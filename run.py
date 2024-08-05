import os
import sys

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from VNPM import app

if __name__ == '__main__':
    app.run(debug=True, port=5001)