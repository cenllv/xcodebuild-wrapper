xcodebuild-wrapper
=============

A script to distribute iPhone Apps to testers using OTA distribution
-----------------------------------------------------------------------------------


xcodebuild-wrapper is a Python script which provide the ability to compile and distribute iPhone apps thought OTA distribution

xcodebuild-wrapper take a lots of parameters:

+ keychain containing your iPhone dev certificate
+ password of this keychain
+ project target
+ project path
+ provisioning profile path
+ sdk
+ developer's name
+ remote host, used to deployment
+ deployment address
+ user name on the deployment host
+ remote password
+ git repository
+ config file

Several log level are available (DEBUG, INFO, WARNING, ERROR, CRITICAL), default value is INFO

Usage:


<blockquote>xcodebuild-wrapper.py --help
usage: xcodebuild-wrapper.py [-h] [-k KEYCHAIN] [-K KEYCHAINPASSWORD]
                             [-p PROJECT] [-P PROVISIONINGPROFILE] [-s SDK]
                             [-c CONFIG] [-n DEVNAME] [-t TARGET] [-d DEPLOY]
                             [-r REMOTEHOST] [-u USERNAME] [-w REMOTEPASSWORD]
                             [-f REMOTEFOLDER] [-g GITREPOSITORY]
                             [-C CONFIGFILE] [--log LOGLEVEL]

xcodebuild wrapper parameters

optional arguments:
  -h, --help            show this help message and exit
  -k KEYCHAIN, --keychain KEYCHAIN
                        Path to the keychain file
  -K KEYCHAINPASSWORD, --keychainPassword KEYCHAINPASSWORD
                        keychain's password
  -p PROJECT, --projectPath PROJECT
                        Path to project file
  -P PROVISIONINGPROFILE, --provisioningProfile PROVISIONINGPROFILE
                        Provisioning Profile path
  -s SDK, --sdk SDK     SDK
  -c CONFIG, --configuration CONFIG
                        Configuration
  -n DEVNAME, --developerName DEVNAME
                        developer name. This information is in the
                        provisionign profile
  -t TARGET, --target TARGET
                        Path to projet's file
  -d DEPLOY, --deploymentAddress DEPLOY
                        Deployment Address, used in manifest.plist file
  -r REMOTEHOST, --remoteHost REMOTEHOST
                        Remote host, used to distribute IPA
  -u USERNAME, --username USERNAME
                        Username on the remote host
  -w REMOTEPASSWORD, --remotePassword REMOTEPASSWORD
                        Password of the username on the remote host
  -f REMOTEFOLDER, --remoteFolder REMOTEFOLDER
                        Destination folder on remote host
  -g GITREPOSITORY, --gitrepository GITREPOSITORY
                        URL of the git repository
  -C CONFIGFILE, --configFile CONFIGFILE
                        Configuration file, instead of each parameter
  --log LOGLEVEL        LogLevel, could be DEBUG | INFO | WARNING | ERROR |
                        CRITICAL. Default value is INFO</blockquote>

Remember, it's open source, feel free to improve.