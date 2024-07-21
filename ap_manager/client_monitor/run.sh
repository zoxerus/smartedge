SCRIPT_PATH="${BASH_SOURCE[0]:-$0}";
cd "$( dirname -- "$SCRIPT_PATH"; )";

[[ "$VIRTUAL_ENV" == "" ]]; INVENV=$?

if [ $INVENV -eq "0" ]  && [ -d ".venv"  ]; then
    echo "sourcing from .venv"

    source ./.venv/bin/activate

    source ~/.bashrc
    alias python='$VIRTUAL_ENV/bin/python'
    alias sudo='sudo '
else echo "running without a virtual environment"
fi 


sudo python ap_manager.py