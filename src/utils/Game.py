import sys
from time import sleep, time
from typing import Union, Optional

from .Console import Console
from .Tower import Tower
from .ActionParser import ActionParser

import pyautogui as pygui
import pytesseract as tesser
from PIL import Image
import keyboard as kb

# Import ImageGrab if possible, might fail on Linux
global use_grab
try:
    from PIL import ImageGrab, ImageOps, ImageEnhance
    use_grab: bool = True
except Exception as e:
    # Some older versions of pillow don't support ImageGrab on Linux
    # In which case we will use XLib
    if (sys.platform == "linux"):
        from Xlib import display, X
        use_grab: bool = False
    else:
        print(f"PIL unavailable for your system.")
        raise e

class Game:
    def __init__(self, settings: dict, mapSettings: dict, console: Console):
        tesser.pytesseract.tesseract_cmd = settings["tesseractPath"]
        self.settings: dict = settings
        self.map: dict = mapSettings
        self.console: Console = console
        self.towers: dict = {}
        self.make_towers()

    def make_towers(self) -> dict:
        self.towers: dict = {}
        for tower in self.map["towers"]:
            self.towers[tower] = Tower(self.map["towers"][tower], self.settings)
        return self.towers

    def start(self) -> bool:
        actionParser: ActionParser = ActionParser(self.towers, self.console, self.settings)
        currRound: int = 0
        restartInst: bool = False
        # Better check for impopable mode by examining the filename
        map_file_path = str(self.map).lower() if hasattr(self.map, "__str__") else ""
        is_impopable = "impopable" in map_file_path
        
        # Initialize timer for periodic level-up check
        last_click_time = time()
        click_interval = 30  # 3 minutes in seconds
        currentRounds = []
        
        if is_impopable:
            print("Detected impopable mode! Will look for insta monkey reward after round 100.")
        
        while restartInst == False:
            # Check if it's time to click in the middle of the screen
            current_time = time()
            if current_time - last_click_time >= click_interval:
                self.click_middle_screen()
                last_click_time = current_time
                # Update progress bar with current status
                if currentRounds and len(currentRounds) >= 2:
                    self.console.progress_bar(int(currentRounds[0]), int(currentRounds[1]))
            
            currentRounds = self.get_round()
            if currentRounds != [] and currRound != currentRounds[0]:
                currentRound = currRound = currentRounds[0]
                if currentRound in self.map["instructions"]:
                    instructions: list[str] = self.map["instructions"][currentRound]
                    for instruction in instructions:
                        #print(instruction)
                        if instruction == "restart":
                            restartInst: bool = True
                            break
                        actionParser.do_action_from_string(instruction)
                self.console.progress_bar(int(currentRound), int(currentRounds[1]))
            sleep(1)
        
        # Use the special restart function with insta monkey collection for impopable difficulty
        # Force collect monkey on round 100 regardless of mode as failsafe
        if int(currentRound) >= 100:
            print(f"Completing round {currentRound}. This is round 100 or higher, so looking for insta monkey reward...")
            return self.restart_game_with_collect_monkey()
        else:
            print(f"Completing round {currentRound}. No insta monkey collection needed.")
            return self.restart_game()

    def restart_game(self) -> bool:
        while "VICTORY" not in (result := (self.get_text(True), self.get_text(False))) and \
                "GAME OVER" not in result:
            sleep(5)
        pygui.moveTo(self.settings["game"]["nextButton"])
        pygui.click()
        sleep(2)
        pygui.moveTo(self.settings["game"]["freeplay"])
        pygui.click()
        sleep(2)
        kb.press_and_release(self.settings["game"]["menuHotkey"])
        sleep(1)
        kb.press_and_release(self.settings["game"]["menuHotkey"])
        sleep(1)
        pygui.moveTo(self.settings["game"]["restartGame"])
        pygui.click()
        sleep(1)
        pygui.moveTo(self.settings["game"]["confirm"])
        pygui.click()
        sleep(1)
        return "VICTORY" in result
        
    def restart_game_with_collect_monkey(self) -> bool:
        # The insta monkey appears before the victory screen
        print("Round 100 completed! Looking for insta monkey reward...")
        
        # First, try to detect and collect the insta monkey
        max_attempts = 20  
        insta_monkey_collected = False
        
        for attempt in range(max_attempts):
            print(f"Attempt {attempt+1}/{max_attempts} to find insta monkey...")
            
            # Take a screenshot of the center area where the insta monkey appears
            screen_width, screen_height = pygui.size()
            center_x = screen_width // 2
            center_y = screen_height // 2
            
            # Try to detect "INSTA MONKEY!" text
            try:
                # Create a region covering the insta monkey area
                insta_region = [center_x - 300, center_y - 200, 600, 400]
                insta_img = self.screen_grab(insta_region)
                
                # Process image for better text detection
                from PIL import ImageEnhance
                enhancer = ImageEnhance.Contrast(insta_img)
                enhanced_img = enhancer.enhance(2.0)
                
                # Try to detect text with OCR
                insta_text = tesser.image_to_string(enhanced_img, config="--psm 6 --oem 3", nice=1)
                print(f"Detected text: {insta_text}")
                
                # Check for keywords
                if any(keyword in insta_text.upper() for keyword in ["INSTA", "MONKEY", "REWARD"]):
                    print("Insta Monkey detected! Clicking to collect...")
                    pygui.moveTo(center_x, center_y)
                    pygui.click()
                    sleep(1)
                    insta_monkey_collected = True
                    break
            except Exception as e:
                print(f"Error during OCR: {str(e)}")
            
            # If we didn't find it yet, wait a bit and try again
            sleep(1)
        
        # If we went through all attempts and didn't find the insta monkey,
        # click in the center anyway as a fallback
        if not insta_monkey_collected:
            print("No insta monkey detected after all attempts. Clicking center as fallback.")
            pygui.moveTo(center_x, center_y)
            pygui.click()
            sleep(1)
        
        # Now wait for the victory screen
        result = None
        print("Waiting for victory screen...")
        for _ in range(30):  # Wait up to 30 seconds for victory screen
            result = (self.get_text(True), self.get_text(False))
            if "VICTORY" in result or "GAME OVER" in result:
                break
            sleep(1)
        
        # Continue with normal restart procedure
        print("Proceeding with game restart...")
        pygui.moveTo(self.settings["game"]["nextButton"])
        pygui.click()
        sleep(2)
        pygui.moveTo(self.settings["game"]["freeplay"])
        pygui.click()
        sleep(2)
        kb.press_and_release(self.settings["game"]["menuHotkey"])
        sleep(1)
        kb.press_and_release(self.settings["game"]["menuHotkey"])
        sleep(1)
        pygui.moveTo(self.settings["game"]["restartGame"])
        pygui.click()
        sleep(1)
        pygui.moveTo(self.settings["game"]["confirm"])
        pygui.click()
        sleep(1)
        return result is not None and "VICTORY" in result

    ### GET ROUND USING PYTESSERACT ###
    def get_round(self) -> str:
        image: Image = self.screen_grab(self.settings["game"]["roundCounter"])
        text: str = tesser.image_to_string(image, config=f"-c tessedit_char_whitelist=0123456789/ --psm 6", nice=1)
        text = ''.join([c for c in text if c in "0123456789/"])
        return text.split('/') if text != '' else []

    def get_text(self, victory: bool = True) -> str:
        if victory:
            image: Image = self.screen_grab(self.settings["game"]["victoryBanner"], "gold")
        else:
            image: Image = self.screen_grab(self.settings["game"]["defeatBanner"], "red")
        text: str = tesser.image_to_string(image, config="--psm 6", nice=1)
        text = ''.join([c for c in text.upper() if c in "VICTORY GAME"])
        return text

    def screen_grab(self, rectangle: list[Union[float, int]], colorFilter: str = 'white'):
        global use_grab
        x, y, width, height = rectangle

        if (use_grab):
            image = ImageGrab.grab(bbox=[x, y, x+width, y+height])

            if colorFilter == "gold":
                image_data = image.getdata()
                new_image_data = []

                for data in image_data:
                    if data[0] == 255 and data[1] in range(212, 256) and data[2] == 0:
                        new_image_data.append((255, 255, 255))
                    else:
                        new_image_data.append((0,0,0))
                image.putdata(new_image_data)

            elif colorFilter == "red":
                image_data = image.getdata()
                new_image_data = []

                for data in image_data:
                    if data[0] == 255:
                        new_image_data.append((255, 255, 255))
                    else:
                        new_image_data.append((0,0,0))
                image.putdata(new_image_data)

            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2)
            image = ImageOps.invert(image)
            image = image.point(lambda x: 0 if x < 10 else 255)
            image = image.convert('L')
        else:
            # ImageGrab can be missing under Linux
            dsp = display.Display()
            root = dsp.screen().root
            raw_image = root.get_image(x, y, width, height, X.ZPixmap, 0xffffffff)
            image = Image.frombuffer(
                "RGB", (width, height), raw_image.data, "raw", "BGRX", 0, 1)

            # TODO: If on linux edit the image to have less noise
        # | Debug Image
        # image.save(f"C:\\Users\\User\\Documents\\temp.png", "PNG")
        return image

    def click_middle_screen(self):
        """
        Clicks in the middle of the screen to handle level-up notifications or any other popup.
        Waits 2 seconds and clicks again to ensure the popup is dismissed.
        """
        screen_width, screen_height = pygui.size()
        center_x = screen_width // 2
        center_y = screen_height // 2
        
        # Quietly perform the clicks without printing messages
        pygui.moveTo(center_x, center_y)
        pygui.click()
        sleep(2)  # Wait 2 seconds between clicks
        pygui.click()  # Click again to ensure the popup is dismissed
