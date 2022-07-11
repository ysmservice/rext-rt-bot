#!/bin/bash
echo "Now setuping..."
cp secret.template.toml secret.toml && cp data.template.toml data.toml
python3 -m pip install -r requirements.txt
git clone https://github.com/RextTeam/rt-lib
mv rt-lib rtlib
cd ./rtlib && python3 -m pip install -r requirements.txt
cd ./common && python3 make_key.py
cd ../../ && mv rtlib/common/secret.key ./
echo "Do you want setup with nano?(y/n)"
read input
if [ $input = "y" ] ; then
    nano secret.json
    nano data.json
else
    echo "ok"
fi
echo "All setup is finish"
