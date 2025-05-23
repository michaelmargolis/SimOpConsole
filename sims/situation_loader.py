import xp
import os

# Default directory for X-Plane saved situations
SITUATIONS_DIR = xp.getSystemPath() + "Output/situations/"
SITUATIONS_FILE = xp.getSystemPath() + "Resources/plugins/PythonPlugins/situations_map.txt"

class SituationLoader:
    def __init__(self):
        self.situations_map = self.load_situations_map()
        # print(self.situations_map)

    def load_situations_map(self):
        """ Reads the situations mapping file and returns a dictionary. """
        situations = {}

        # Check if the file exists
        if not os.path.exists(SITUATIONS_FILE):
            xp.log(f"[ERROR] Situations map file not found: {SITUATIONS_FILE}")
            return situations

        try:
            with open(SITUATIONS_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):  # Skip empty lines or comments
                        continue
                    
                    parts = line.split(",")
                    if len(parts) != 2:
                        xp.log(f"[WARNING] Invalid line format in situations file: {line}")
                        continue

                    try:
                        flight_enum = int(parts[0].strip())
                        filename = parts[1].strip()
                        situations[flight_enum] = filename
                    except ValueError:
                        xp.log(f"[ERROR] Invalid enum values in line: {line}")

        except Exception as e:
            xp.log(f"[ERROR] Failed to read situations file: {str(e)}")

        return situations

    def get_situation_file(self, flight_enum):
        """ Returns the corresponding situation filename or None if not found. """
        return self.situations_map.get(flight_enum, None)

    def is_paused(self):
        """ Checks if X-Plane is currently paused. """
        pause_dataref = xp.findDataRef("sim/time/paused")
        return xp.getDatai(pause_dataref) if pause_dataref else 0

    def load_situation(self, flight_enum):
        """ Loads the selected situation file and ensures X-Plane is not in replay mode. """
        filename = self.get_situation_file(flight_enum)
        
        if filename is None:
            xp.log(f"[ERROR] No situation found for flight={flight_enum}")
            return

        filepath = os.path.join(SITUATIONS_DIR, filename)
        
        if not os.path.exists(filepath):
            xp.log(f"[ERROR] Situation file not found: {filepath}")
            return

        # ✅ Log Replay Mode Before Loading
        replay_mode_ref = xp.findDataRef("sim/time/replay_mode")
        if replay_mode_ref:
            initial_replay_state = xp.getDatai(replay_mode_ref)
            xp.log(f"[DEBUG] Replay mode BEFORE loading: {initial_replay_state}")

        # Load the situation file
        ret = xp.loadDataFile(xp.DataFile_Situation, filepath)
        if ret:
            xp.log(f"[INFO] Successfully loaded situation: {filepath}")

            # ✅ Log Replay Mode After Loading
            if replay_mode_ref:
                replay_after = xp.getDatai(replay_mode_ref)
                xp.log(f"[DEBUG] Replay mode AFTER loading: {replay_after}")

                # ✅ If replay mode is still active, force disable it
                if replay_after == 1:
                    xp.log("[WARNING] Replay mode is still active. Attempting to disable it.")
                    xp.setDatai(replay_mode_ref, 0)
                    replay_after_fix = xp.getDatai(replay_mode_ref)
                    xp.log(f"[DEBUG] Replay mode after disabling attempt: {replay_after_fix}")

            # ✅ Pause if necessary
            if not self.is_paused():
                xp.log("[INFO] Sim is running. Pausing X-Plane.")
                pause_cmd = xp.findCommand("sim/operation/pause_toggle")
                xp.commandOnce(pause_cmd)
            else:
                xp.log("[INFO] Sim is already paused.")
        else:
            xp.log(f"[ERROR] Failed to load situation: {filepath}")


