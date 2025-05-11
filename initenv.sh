git pull

VENV_PATH="venv"

if [ ! -d "$VENV_PATH" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv $VENV_PATH
fi
source $VENV_PATH/bin/activate
python -m pip install -r requirements.txt