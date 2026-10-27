"""Start Luminaz locally:  py -3 run.py   then open http://127.0.0.1:5000"""
import os, sys
from luminaz import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print("Luminaz running at http://127.0.0.1:%d  (Ctrl+C to stop)" % port)
    app.run(host="127.0.0.1", port=port, debug="--debug" in sys.argv)
