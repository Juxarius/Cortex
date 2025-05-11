from pathlib import Path
import json

CHOICES_FILE_PATH = Path(__file__).parent / 'choices.json'
WORLD_TXT_FILE_PATH = r"D:\Coding Projects\ao-bin-dumps\formatted\world.txt"

def contains_digits(s: str) -> bool:
    return any(char.isdigit() for char in s)

def update_locations() -> None:
    with open(WORLD_TXT_FILE_PATH, 'r') as f:
        lines = f.readlines()
        locations = [line.split(":")[-1].strip() for line in lines]
        [print(l) for l in locations if contains_digits(l)]
        locations = sorted(set(l for l in locations if l != '' and not contains_digits(l)))
    with open(CHOICES_FILE_PATH, 'r') as f:
        choices = json.load(f)
    choices['locations'] = locations
    with open(CHOICES_FILE_PATH, 'w') as f:
        json.dump(choices, f, indent=4)

if __name__ == "__main__":
    update_locations()
