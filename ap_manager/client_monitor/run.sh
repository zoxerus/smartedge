SCRIPT_PATH="${BASH_SOURCE[0]:-$0}";
cd "$( dirname -- "$SCRIPT_PATH"; )";

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "This file must be sourced in the terminal with . ${0} instead of calling it"
    exit

fi

[[ "$VIRTUAL_ENV" == "" ]]; INVENV=$?

if [ $INVENV -eq "0" ]; then
    if [ -d ".venv"  ]; then
        echo "sourcing from .venv"

        . ./.venv/bin/activate

        source ~/.bashrc
        alias python='$VIRTUAL_ENV/bin/python'
        alias sudo='sudo '
    fi
else
    alias python='$VIRTUAL_ENV/bin/python'
    alias sudo='sudo '
fi 

sudo python ap_manager.py


