"""build_all.py — deterministic full build. Exits nonzero on stage failure."""
import bpy, importlib, os, sys, traceback
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import config as C

STAGES = ["00_bootstrap_scene", "40_build_materials", "10_build_architecture",
          "20_build_pool_table", "22_build_balls_and_rack", "30_build_bar",
          "50_set_dress", "55_age_and_story", "56_build_patron_footprints",
          "60_build_lighting",
          "70_build_cameras",
          "75_build_sweep"]

def save(tag):
    p = os.path.join(C.ROOT, "blend", "checkpoints", tag + ".blend")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=p)

def main():
    mats = None
    for s in STAGES:
        print("[stage] %s" % s)
        try:
            m = importlib.import_module(s)
            importlib.reload(m)
            if s == "40_build_materials":
                mats = m.build()
            elif s in ("00_bootstrap_scene", "22_build_balls_and_rack"):
                m.build()
            else:
                m.build(mats)
        except Exception:
            traceback.print_exc()
            print("STAGE FAILED: %s" % s); sys.exit(2)
    save("02_table_geometry")
    master_path = os.path.join(C.ROOT, "blend", "poolroom_master.blend")
    bpy.ops.wm.save_as_mainfile(filepath=master_path)
    v = importlib.import_module("90_validate_scene"); importlib.reload(v)
    dimensional_ok = v.run()
    r = importlib.import_module("95_audit_realism"); importlib.reload(r)
    realism = r.run()
    realism_ok = realism["summary"]["required_failures"] == 0
    s = importlib.import_module("96_audit_environment_staging")
    importlib.reload(s)
    staging = s.run()
    staging_ok = staging["summary"]["required_failures"] == 0
    lock_path = os.path.join(C.ROOT, "reports", "environment_lock.json")
    lock_ok = True
    if os.path.exists(lock_path):
        lock = importlib.import_module("98_validate_environment_lock")
        importlib.reload(lock)
        lock_ok = lock.run(write=False)
        if lock_ok:
            # Rebuilt collections start selectable. Reinstate the saved-master
            # guard only after their fingerprints match the approved baseline.
            bpy.ops.wm.save_as_mainfile(filepath=master_path)
    else:
        print("[environment lock] baseline not established yet; run "
              "98_validate_environment_lock.py -- --write after approval")
    ok = dimensional_ok and realism_ok and staging_ok and lock_ok
    print("BUILD OK" if ok else "BUILD COMPLETED WITH REQUIRED FAILURES")
    sys.exit(0 if ok else 1)

main()
