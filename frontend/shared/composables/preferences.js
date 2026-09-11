const key = "theumst.magical-lofi.preferences.v1";
export function readPreferences() {
  try {
    return JSON.parse(localStorage.getItem(key)) || {};
  } catch {
    return {};
  }
}
export function savePreferences(patch) {
  try {
    localStorage.setItem(
      key,
      JSON.stringify({ ...readPreferences(), ...patch }),
    );
    return true;
  } catch {
    return false;
  }
}
