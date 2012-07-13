#!/usr/bin/python2.7
# -*-coding:utf-8 -*-

# -------------------------------------------------------
# Script d'appel de xcodebuild pour jenkins
# -------------------------------------------------------

# -------------------------------------------------------
# Author	: Jacques Foucry
# Date		: 05-03-2012
# Goal		: This script checkout (with git) a xcodeproj
# compile the project with a provisionning profile then
# sent the IPA to a web server in order to disbutir in OTA
# -------------------------------------------------------
#
# -------------------------------------------------------
# Modification:
# Author	: Jacques Foucry
# Date		: 06-09-2012
# Goal		: new feature, read a config file instead of
# read them from CLI
# 
# The parameters will be look in this order:
# 1) cli parameters
# 2) config files parameters
# 3) default value (if apply)
#
# That's mean that no more parameters in cli are 
# required. The required status must be traited
# ------------------------------------------------------

import logging
import os
import shutil
import sys
#import datetime
import time
import argparse
import time
import zipfile
import subprocess
import fnmatch
import plistlib
import urlparse
import string
import git
import ConfigParser

# --- Parameters definition
def writeOnSTDERR(msg):
        sys.stderr.write(msg)

# --- Check if a parameter is present into config file
def checkParameter(parameter):
	logger.debug("checkParameter: parameter = %s"% parameter)
	try:
		value = config.get("xcodebuild","%s" % parameter)
	except ConfigParser.NoOptionError:
		logger.debug("%s not found in config file" % parameter)
		value=None
		
	return value

# --- Checks presence of a file
def checkPresence(file):
	logger.debug("checkPresence: file = %s"% file)
	try:
		os.path.exists(file)
	except OSError as e:
		logger.debug("%s cannot be found, please check your path.  Exiting"% file) 	
		logger.info("Error String =="+e.strerror+" Error Num == %d", e.errno)
		return 1

# --- Opening keychain

def openKeychain(password, keychain):
	logger.debug("openKeychain: password = *******, keychain = %s"% keychain)
	cmd_string=" ".join(["/usr/bin/security","unlock-keychain", "-p", password, keychain])
	try:
		subprocess.check_call(["/usr/bin/security","unlock-keychain","-p", password, keychain])
	except OSError as e:
		logger.debug("Error in %s, exiting"% (cmd_string))
		wrieOnSTDERR("Cannot open Keychain %s. See log for more details" % keychain)
		sys.exit(1)

	cmd_string=" ".join(["/usr/bin/security", "default-keychain","-d","user", "-s", keychain])
	try:
		subprocess.check_call(["/usr/bin/security", "default-keychain","-d","user", "-s", keychain])
	except OSError as e:
		logger.debug("Error in %s, exiting"% (cmd_string))

	subprocess.check_call(["/usr/bin/security", "default-keychain"])

# --- Compiling

def compileApp(SDK, projectPath, configuration, target):
	logger.debug("compileApp: SDK = %s projectPath = %s, configuration = %s, target = %s"%(SDK, projectPath, configuration, target))
	cmd_string=" ".join(["/usr/bin/xcodebuild","-sdk",SDK,"-project ",projectPath,"-configuration",configuration, "-target", target])
	try:
		subprocess.check_call(["/usr/bin/xcodebuild","-sdk", SDK, "-project", projectPath,"-configuration", configuration, "-target", target])
	except OSError as e:
		logger.debug("Error in %s. Exiting"%(cmd_string)) 
		wrieOnSTDERR("Cannot compile App. See log for more details")
		sys.exit(1)
	
# --- Transforming .app into .ipa 

def createIPA(SDK, workspace, configuration, target, DeveloperName, provisioningProfile,targetFolder,appPath):
	logger.debug("createIPA: SDK= %s, workspace = %s, configuration = %s, target = %s, DeveloperName = %s, provisioningProfile = %s, targetFolder = %s, appPath = %s"%(SDK, workspace, configuration,target,DeveloperName, provisioningProfile,targetFolder,appPath))
	cmd_string=" ".join(["/usr/bin/xcrun","-sdk",GSDK, "PackageApplication", "-v"," %s/%s.app"% (appPath,target),"-o","%s/%s.ipa"%(targetFolder,target),"-sign","\"%s\""%(DeveloperName), "-embed","\"%s\""%(provisioningProfile)]) 
	logger.info(cmd_string) 
	try:
		subprocess.check_call(cmd_string,shell=True)
	except OSError as e:
		logger.debug("Error in %s. Exiting"% (cmd_string))
		logger.info(" Error String =="+e.strerror+" Error Num == %d", e.errno)
		wrieOnSTDERR("Cannot create IPA. See log for more details")
		sys.exit(1)

def retreiveInfo(targetFolder,target):
	logger.debug("retreiveInfo: targetFolder = %s, target = %s" %(targetFolder, target))
	zin=zipfile.ZipFile("/%s/%s.ipa"%(targetFolder,target))
	logger.debug(zin)
	for item in zin.namelist():
		if fnmatch.fnmatch(item, '*/Info.plist'): 
			filename = os.path.basename(item)
			filename = "/%s/%s"%(targetFolder,filename)
			inFile = zin.open(item)
			outFile = file(filename, "wb")
			shutil.copyfileobj(inFile,outFile)
			inFile.close()
			outFile.close()
	return filename

def createManifest(info,target,targetFolder,deployment_address):
	logger.debug("createManifest: info = %s, target = %s, targetFolder = %s, deployment_address = %s"% (info, target, targetFolder, deployment_address))
	xmlfile="/%s/%s.xml"%(targetFolder,target)
	# we need to convert Info.plist into a xml file (by default it's a binary plist)
	subprocess.Popen('plutil -convert xml1 -o %s %s'%(xmlfile,info),shell=True).wait()
	infoPlistFile = open(xmlfile, 'r')
	app_plist = plistlib.readPlist(infoPlistFile)
	os.remove(xmlfile)
	manifestFilename='/%s/manifest.plist'%(targetFolder)
	
	logger.debug(deployment_address)

	manifest_plist= {
		'items' : [
			{
				'assets' : [
					{
						'kind' : 'software-package',
						'url' : urlparse.urljoin(deployment_address, target + '.ipa'),
					}
				],
				'metadata' : {
					'bundle-identifier' : app_plist['CFBundleIdentifier'],
					'bundle-version' : app_plist['CFBundleVersion'],
					'kind' : 'software',
					'title' : app_plist['CFBundleName'],
				}
			}
		]
	}
	plistlib.writePlist(manifest_plist, manifestFilename)
	return manifestFilename

def fillHTML(app_name,manifest):
	logger.debug("fillHTML: app_name = %s, manifest = %s" % (app_name,manifest))
	manifestPath="%s%s"%(deployment_address,manifest)
	template_html="""
	<!DOCTYPE html PUBLIC "-//WC3/DTD HTML 1.0 Transitional/EN" "http://www.w3c.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
	<html xmlns="http://www.w3.org/1999/xhtml">
	<head>
	<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
	<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0">
	<title>[BETA_NAME] - Beta Release</title>
	<style type="text/css">
	body {background:#fff;margin:0;padding:0;font-family:arial,helvetica,sans-serif;text-align:center;padding:10px;color:#333;font-size:16px;}
	#container {width:300px;margin:0 auto;}
	h1 {margin:0;padding:0;font-size:14px;}
	p {font-size:13px;}
	.link {background:#ecf5ff;border-top:1px solid #fff;border:1px solid #dfebf8;margin-top:.5em;padding:.3em;}
	.link a {text-decoration:none;font-size:15px;display:block;color:#069;}
	
	</style>
	</head>
	<body>
	
	<div id="container">
	
	<h1>Dear testers</h1>
	
	<div class="link"><a href="itms-services://?action=download-manifest&url=[DEPLOYMENT_PATH]">Tap here to install<br />[BETA_NAME]<br />On Your Device</a></div>
	
	<p><strong>Link didn't work?</strong><br />
	Make sure you're visiting this page on your device, not your computer.</p>
	
	</body>
	</html>
	"""
	TEMPLATE_PLACEHOLDER_NAME = '[BETA_NAME]'
	TEMPLATE_PLACEHOLDER_DEPLOYMENT_PATH = '[DEPLOYMENT_PATH]'
	template_html = string.replace(template_html, TEMPLATE_PLACEHOLDER_NAME, app_name)
	template_html = string.replace(template_html, TEMPLATE_PLACEHOLDER_DEPLOYMENT_PATH, manifestPath)
	return template_html

def createIndexHTML(targetFolder,target,manifest):
	logger.debug("createIndexHTML: targetFolder = %s, target = %s, manifest = %s" %(targetFolder, target, manifest))
	indexFilename = '/%s/index.html'%(targetFolder)
	manifest=os.path.basename(manifest)
	indexFile = open(indexFilename, 'w')
	indexFile.write(fillHTML(target,manifest))
	return indexFilename

def createTargetFolder(folder):
	logger.debug("createTargetFolder: folder = %s"% folder)
	try:
		subprocess.call(["/bin/mkdir", folder])
	except OSError as e:
		if os.path.exists(folder):
			logger.info("%s folder already exist, Exiting")
			logger.debug("ErrorString == %s ErrorNum == %d"% (e.strerror,e.errno))
			pass
		else:
			raise Exception("Error in creating %s folder"% (folder))
			writeOnSTDERR("Cannot create target folder %s. See log for more details" % folder)
			sys.exit(1)

def distribution(server, user, password,distantFolder,sourceFolder):
	cmd_string=" ".join(["/usr/bin/scp", "-r", "%s/*"%(targetFolder),  "%s@%s:%s"%(user,server,distantFolder)])
	try:
		subprocess.check_call(cmd_string,shell=True)
	except OSError as e:
		logger.debug(cmd_string)
		logger.debug("ErrorString == %s ErrorNum == %d"% (e.strerror,e.errno))
 
#def sourceFolderCheck(sourcePath):


def gitClone(gitRepository, projectPath):
	logger.debug("gitClone: gitRepository = %s, projectPath = %s" % (gitRepository, projectPath))
	git.Repo.clone_from(gitRepository,projectPath)

def gitPull(projectPath):
	logger.debug("gitPull: projectPath = %s" % projectPath)
	os.chdir(projectPath)
	repo = git.Repo(projectPath)
	repo.remotes.origin.pull()


parser = argparse.ArgumentParser(description='xcodebuild wrapper parameters')

parser.add_argument('-k', '--keychain', action="store", dest="keychain", help="Path to the keychain file")
parser.add_argument('-K', '--keychainPassword', action="store", dest="keychainPassword", help="keychain's password")

parser.add_argument('-p', '--projectPath', action="store", dest="project", help="Path to project file")
parser.add_argument('-P', '--provisioningProfile', action="store", dest="ProvisioningProfile", help="Provisioning Profile path")
parser.add_argument('-s', '--sdk', action="store", dest="sdk", help="SDK")
parser.add_argument('-c', '--configuration', action="store", dest="config", help="Configuration")
parser.add_argument('-n', '--developerName', action="store", dest="devname", help="developer name. This information is in the provisionign profile")
parser.add_argument('-t', '--target', action="store", dest="target", help="Path to projet's file")
parser.add_argument('-d', '--deploymentAddress', action="store", dest="deploy", help="Deployment Address, used in manifest.plist file")
parser.add_argument('-r', '--remoteHost', action="store", dest="remoteHost", help="Remote host, used to distribute IPA")
parser.add_argument('-u', '--username', action="store", dest="username", help="Username on the remote host")
parser.add_argument('-w', '--remotePassword', action="store", dest="remotePassword", help="Password of the username on the remote host")
parser.add_argument('-f', '--remoteFolder', action="store", dest="remoteFolder", help="Destination folder on remote host")
parser.add_argument('-g', '--gitrepository', action="store", dest="gitRepository", help="URL of the git repository")
parser.add_argument('-C', '--configFile', action="store", dest="configFile", help="Configuration file, instead of each parameter")

parser.add_argument('--log', action="store", dest="logLevel", help="LogLevel, could be DEBUG | INFO | WARNING | ERROR | CRITICAL. Default value is INFO", default="INFO")


args = parser.parse_args()

configFile = args.configFile

# --- Logger initialization

logger = logging.getLogger('xcodebuild-wrapper')
logHandler = logging.FileHandler('/tmp/xcodebuild-wrapper.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
configFilePresent = False
logger.info("Debut du programme")

# --- LogLevel

logLevel = args.logLevel
if logLevel=="DEBUG":
	logger.setLevel(logging.DEBUG)
elif logLevel=="INFO":
	logger.setLevel(logging.INFO)
elif logLevel=="WARNING":
	logger.setLevel(logging.WARNING)
elif logLevel=="ERROR":
	logger.setLevel(logging.ERROR)
elif logLevel=="CRITICAL":
	logger.setLevel(logging.CRITICAL)
else:
	logger.info('Unkown loglevel '+ debugLevel +', using INFO')

if configFile is not None:
	if (os.path.exists(configFile)):
		config = ConfigParser.RawConfigParser()
		config.read("%s" % configFile)
		configFilePresent = True


numberOfError = 0
errorString=""

# Required
keychain = args.keychain
if keychain is None:
	logger.debug("keychain is None")
	if configFilePresent is True:
		logger.debug("configFilePresent is True") 
		keychain = checkParameter("keychain")
		logger.debug("Keychain value is: %s" % keychain)
	if keychain is None:
		logger.debug("keychain is None")
		errorString = "Keychain"
		++numbeOfError

# Required
password = args.keychainPassword
if password is None:
	if configFilePresent is True:
		password = checkParameter("password")
		logger.debug("Keychain password is: %s" % password)
	if password is None:
		errorString = errorString + ", password"
		numberOfError += 1

# Required
projectPath = args.project
if projectPath is None:
	if configFilePresent is True:
		projectPath = checkParameter("projectPath")
		logger.debug("Project Path is : %s" % projectPath)
	if projectPath is None:
		errorString = errorString + " projectPath"
		numberOfError += 1

# Required
SDK = args.sdk
if SDK is None:
	if configFilePresent is True:
		SDK = checkParameter("SDK")
		logger.debug("SDK is: %s" % SDK)
	if SDK is None:
		errorString = errorString + " SDK"
		numberOfError += 1

# Required
target = args.target
if target is None:
	if configFilePresent is True:
		target = checkParameter("target")
		logger.debug("target is: %s" % target)
	if target is None:
		errorString 
		numberOfError
		errorString = errorString + " target"
		numberOfError += 1

# Required
configuration = args.config
if configuration is None:
	if configFilePresent is True:
		configuration = checkParameter("configuration")
		logger.debug("configuration is: %s" % configuration)
	if configuration is None:
		errorString = errorString + " configuration"
		numberOfError += 1

# Required
developerName = args.devname
if developerName is None:
	if configFilePresent is True:
		developerName = checkParameter("developerName")
		logger.debug("developerName is: %s" % developerName)
	if developerName is None:
		errorString = errorString + " developerName"
		numberOfError += 1

# Required
provisioningProfile = args.ProvisioningProfile
if provisioningProfile is None:
	if configFilePresent is True:
		provisioningProfile = checkParameter("provisioningProfile")
		logger.debug("provisioningProfile is: %s" % provisioningProfile)
	if provisioningProfile is None:
		errorString = errorString + " provisioningProfile"
		numberOfError += 1

# Required
deployment_address = args.deploy
if deployment_address is None:
	if configFilePresent is True:
		deployment_address = checkParameter("deployment_address")
		logger.debug("deployment_address is: %s" % deployment_address)
	if deployment_address is None:
		errorString = errorString + " deployment_address"
		numberOfError += 1

# remoteHost is not mandatory
remoteHost= args.remoteHost
if remoteHost is None:
	if configFilePresent is True:
		remoteHost = checkParameter("remoteHost")
		logger.debug("remoteHost is: %s" % remoteHost)
	#if remotehost is None:
	#	errorString = errorString + " remotehost"
	#	numberOfError=+1

# username is not mandatory
username = args.username
if username is None:
	if configFilePresent is True:
		username = checkParameter("username")
		logger.debug("username is: %s" % username)
	#if username is None:
	#	errorString = errorString + " username"
	#	numberOfError=+1

# remotePassword is not mandatory
remotePassword = args.remotePassword
if remotePassword is None:
	if configFilePresent is True:
		remotePassword = checkParameter("remotePassword")
		logger.debug("remotePassword is: %s" % remotePassword)

# remoteFolder is not mandatory
remoteFolder = args.remoteFolder
if remoteFolder is None:
	if configFilePresent is True:
		remoteFolder = checkParameter("remoteFolder")
		logger.debug("remoteFolder is : %s" % remoteFolder)

# gitRepository is not mandatory
gitRepository = args.gitRepository
if gitRepository is None:
	if configFilePresent is True:
		gitRepository = checkParameter("gitRepository")
		logger.debug("gitRepository is : %s" % gitRepository)

if numberOfError > 1:
	errorString = errorString+" are mandatory"
elif numberOfError == 1:
	errorString = errorString+" is mandatory"

logger.debug("numberOfError = %d" % numberOfError)
logger.debug("errorString == %s" % errorString)

if numberOfError > 0:
	logger.info("Error in parameters. Check the log file, rerun with DEBUG log level")
	sys.exit(1)


# -- timestamp is used to create de unique target folder
timestamp = int(time.time())
targetFolder="/tmp/%s-%d"%(target,timestamp)
logger.debug("targetFolder == %s"%(targetFolder))

# --- find project path
workspace=os.path.dirname(projectPath)


###### ----- must add a test to be sure that deployment_address ends with a /
if deployment_address[-1:] != '/':
	deployment_address = deployment_address+'/'
	logger.debug("added / at the end of deployment_address: %s"%(deployment_address))

# -- gsdk is sdk without version (iphoneos5.0 -> iphoneos)
GSDK = SDK[:-3]
logger.debug("GSDK == %s"%(GSDK))

# -- appPath is the path to the generated app 
appPath="%s/build/%s-%s"%(workspace,configuration,GSDK)
logger.debug("appPath == %s"%(appPath))

# --- check presence of the keychain and the project
if checkPresence(projectPath) is not 1:
	if checkPresence("%s/.git"%(workspace)):
		if gitrepository:
			gitclone(gitRepository,workspace)
		else:
			gitpull(workspace)	

# --- openning the keychain
if checkPresence(keychain) is not 1:
	openKeychain(password, keychain)

	# --- create the target folder in /tmp
createTargetFolder(targetFolder)

	# --- compile to .app
compileApp(SDK, projectPath, configuration, target)

	# --- transforme the .app into .ipa (in targetfolder)
createIPA(SDK, workspace, configuration, target, developerName, provisioningProfile,targetFolder, appPath)

	# --- Extract Info.plsit form .ipa file
info=retreiveInfo(targetFolder,target)

	# --- Create Manifest.plist
manifest=createManifest(info,target,targetFolder,deployment_address)

	# --- Create index.hml file
htmlFile=createIndexHTML(targetFolder,target,manifest)

	# --- Send files on distribution machine
distribution(remoteHost, username, password, remoteFolder, targetFolder)

