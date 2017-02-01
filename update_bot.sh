sudo git pull
sudo python3.5 -m pip install --upgrade pip
sudo python3.5 -m pip install --upgrade -r requirements.txt

clear

read -p "Update complete, would you like to run the bot? (yes/no)" reply

choice=$(echo $reply|sed 's/(.*)/L1/')

if [ "$choice" = 'yes' ] 
then
  clear
  sudo sh run.sh

elif [ "$choice" = 'no'  ]
then
  echo "You selected 'no', hence exiting in 3 seconds";
  sleep 3
  exit 0
else
echo "invalid answer, type yes or no";
fi
