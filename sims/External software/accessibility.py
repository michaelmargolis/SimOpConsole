# from XPLMDataAccess import XPLMFindDataRef, XPLMSetDataf, XPLMSetDatai

ACCESSIBILITY_FILE = "Resources/plugins/PythonPlugins/accessibility.txt"

def load_accessibility_settings(file_path=ACCESSIBILITY_FILE):
    """
    Parses the accessibility.txt file with format:
    dataref, HIGH_value, MODERATE_value, NONE_value
    Lines with invalid formatting or missing values are ignored.
    """
    levels = ["HIGH", "MODERATE", "NONE"]
    settings = {level: {} for level in levels}

    try:
        with open(file_path, "r") as file:
            for line_num, line in enumerate(file, start=1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                line = line.split("#")[0].strip()

                # Split at the first "=" only
                if '=' not in line:
                    print(f"⚠️ Skipping line {line_num}: Missing '=' — '{line}'")
                    continue

                dataref, value_str = map(str.strip, line.split("=", 1))
                parts = [p.strip() for p in value_str.split(",")]

                if len(parts) != 3:
                    print(f"⚠️ Skipping line {line_num}: Expected 3 values after '=', got {len(parts)} — '{line}'")
                    continue

                try:
                    high_val = float(parts[0]) if "." in parts[0] else int(parts[0])
                    mod_val = float(parts[1]) if "." in parts[1] else int(parts[1])
                    none_val = float(parts[2]) if "." in parts[2] else int(parts[2])
                except ValueError:
                    print(f"⚠️ Invalid value format on line {line_num}: '{line}'")
                    continue

                settings["HIGH"][dataref] = high_val
                settings["MODERATE"][dataref] = mod_val
                settings["NONE"][dataref] = none_val

    except FileNotFoundError:
        print(f"❌ ERROR: Accessibility config file not found at: {ACCESSIBILITY_FILE}")

    return settings


def set_accessibility(level):
    """
    Applies all DataRef values for the specified accessibility level (HIGH, MODERATE, NONE).
    """
    level = level.upper()
    settings = load_accessibility_settings()

    if level not in settings:
        print(f"❌ ERROR: Invalid accessibility level '{level}'")
        return

    print(f"Applying accessibility settings for level: '{level}'")

    for dataref, value in settings[level].items():
        ref = XPLMFindDataRef(dataref)
        if not ref:
            print(f"⚠️ DataRef not found: {dataref}")
            continue

        if isinstance(value, float):
            XPLMSetDataf(ref, value)
        else:
            XPLMSetDatai(ref, value)

    print(f"Accessibility level '{level}' applied successfully.")
