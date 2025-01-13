import re
import sys
import threading
import time
import click


def extract_xml_content(text, tag_name):
    """
    Extract content between specified XML tags from a string.

    Args:
        text (str): The input string containing XML tags
        tag_name (str): The name of the tag to extract content from

    Returns:
        str: The content between the tags, or None if no match is found
    """
    pattern = f"<{tag_name}>(.*?)</{tag_name}>"
    match = re.search(pattern, text, re.DOTALL)

    return match.group(1) if match else None


class Spinner:
    """A simple spinner class to show activity"""

    def __init__(self, message="", delay=0.1):
        self.spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.delay = delay
        self.busy = False
        self.spinner_visible = False
        self.message = message
        self.current = 0
        self._screen_lock = threading.Lock()
        self.thread = None
        sys.stdout.write(f"\r")

    def write_next(self):
        with self._screen_lock:
            if not self.spinner_visible:
                sys.stdout.write(
                    f"\r{click.style(self.spinner[self.current], fg='bright_blue')} {self.message}"
                )
                self.current = (self.current + 1) % len(self.spinner)
                sys.stdout.flush()

    def run(self):
        while self.busy:
            self.write_next()
            time.sleep(self.delay)

    def start(self):
        self.busy = True
        self.current = 0
        self._screen_lock = threading.Lock()
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def stop(self):
        self.busy = False
        time.sleep(self.delay)
        if self.thread:
            self.thread.join()
        sys.stdout.write("\r")
        sys.stdout.write("\n")
