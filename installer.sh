#!/bin/bash
#=====================================================================#
#                    Setup Open Data Infrastructure                   #
#=====================================================================#
# This script sets up an instance of the Open Data Infrastructure in  #
# a server.
#=====================================================================#

set -o errexit
set -o nounset

#-------------- Colour codes ---------------#
readonly red=$'\e[1;31m'
readonly grn=$'\e[1;32m'
readonly yel=$'\e[1;33m'
readonly blu=$'\e[1;34m'
readonly mag=$'\e[1;35m'
readonly cyn=$'\e[1;36m'
readonly end=$'\e[0m'

# Check that /opt/odi doesn't exist

if [ -d /opt/odi ]; then
  echo "/opt/odi already exists!"
  exit 1
fi

echo "${cyn}=========================================${end}"
echo "${cyn}===     Open Data Infrastructure      ===${end}"
echo "${cyn}=========================================${end}"

user="$(whoami)"
echo "${user}" > /tmp/odi.user

echo "This script will do the following:"
echo "    1) add user ${user} as sudo without password"
echo "    2) install ODI dependencies including git, python3 and docker"
echo "    3) clone ODI repository to /opt/odi"


read -p "Do you want to continue? (yes/no): " choice
# Check the user's choice
if [ "$choice" = "yes" ]; then
    echo "Installing..."
    # Add your code here for the continuation
elif [ "$choice" = "no" ]; then
    echo "${red}Exiting...${end}"
    exit 0
else
    echo "Invalid choice. Please enter 'yes' or 'no'."
fi

echo "Swithing to root..."

sudo -s <<EOF

user=$(cat /tmp/odi.user)
rm /tmp/odi.user
sudoers_file="/etc/sudoers.d/${user}"
if [ ! -f sudoers_file ]; then
    echo "${user} ALL=(ALL) NOPASSWD:ALL" > sudoers_file
fi

echo "installing dependencies"
apt update && sudo apt upgrade -y
apt install git python3 python3-pip ca-certificates curl


echo "installing docker"
apt-get update
apt-get install ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "Adding user ${user} to docker group"
usermod -aG docker ${user}
mkdir /opt/odi
chown -R ${user}:${user} /opt/odi
ln -s /opt/odi/odi_manager.py /usr/local/bin/odi
EOF

echo "Back to user ${user}"

echo "cloning open-data-infrastructure"
git clone "https://github.com/EnocMartinez/open-data-infrastructure" /opt/odi
cd /opt/odi

echo "${yel}switching to development version!${end}"
git checkout develop
git pull --all
echo "Installing python3 packages"
pip3 install -r requirements.txt --break-system-packages

