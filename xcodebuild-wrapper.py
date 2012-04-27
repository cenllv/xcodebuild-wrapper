#!/usr/bin/python2.7
# -*-coding:utf-8 -*-

# Licence Creativ Common BY - SA http://creativecommons.org/licenses/by-sa/3.0/
#
# Auteur 	: Jacques Foucry
# Date		: 2012-04-11
#
# -------------------------------------------------------
# Script d'appel de xcodebuld pour jenkins
# ------------------------------------------------------

import logging
import os
import shutil
import sys
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

# --- Préparation des parametres nécesaire

parser = argparse.ArgumentParser(description='xcodebuild wrapper parameters')

parser.add_argument('-k', '--keychain', action="store", required=True, dest="keychain", help="Path to the keychain file")
parser.add_argument('-K', '--keychainPassword', action="store", required=True, dest="keychainPassword", help="keychain's password")

parser.add_argument('-p', '--projectPath', action="store", required=True, dest="project", help="Path to project file")
parser.add_argument('-P', '--provisionningProfile', action="store", required=True, dest="ProvisionProfile", help="Provisionning Profile path")
parser.add_argument('-s', '--sdk', action="store", required=True, dest="sdk", help="SDK")
parser.add_argument('-c', '--configuration', action="store", required=True, dest="config", help="Configuration")
parser.add_argument('-n', '--developerName', action="store", required=True, dest="devname", help="Developer name. This information is in the provisionign profile")
parser.add_argument('-t', '--target', action="store", required=True, dest="target", help="Path to projet's file")
parser.add_argument('-d', '--deploymentAddress', action="store", required=True, dest="deploy", help="Deployment Address, used in manifest.plist file")
parser.add_argument('-r', '--remoteHost', action="store", dest="remoteHost", help="Remote host, used to distribute IPA")
parser.add_argument('-u', '--username', action="store", dest="username", help="Username on the remote host")
parser.add_argument('-w', '--remotePassword', action="store", dest="remotePassword", help="Password of the username on the remote host")
parser.add_argument('-f', '--remoteFolder', action="store", dest="remoteFolder", help="Destination folder on remote host")
parser.add_argument('-g', '--gitrepository', action="store", dest="gitRepository", help="URL of the git repository")

parser.add_argument('--log', action="store", dest="logLevel", help="LogLevel, could be DEBUG | INFO | WARNING | ERROR | CRITICAL. Default value is INFO", default="INFO")

args= parser.parse_args()

keychain = args.keychain
password = args.keychainPassword

project = args.project
SDK = args.sdk
target = args.target
logLevel = args.logLevel
configuration = args.config
DeveloperName = args.devname
ProvisionningProfile = args.ProvisionProfile
deployment_address = args.deploy
remoteHost= args.remoteHost
username = args.username
remotepassword = args.remotePassword
remoteFolder = args.remoteFolder
gitRepository = args.gitRepository

# --- Find Project path
workspace=os.path.dirname(project)

# --- Logger initialization
logger = logging.getLogger('xcodebuild-wrapper')
logHandler = logging.FileHandler('/tmp/xcodebuild-wrapper.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

# --- LogLevel

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


if deployment_address[-1:] != '/':
	deployment_address = deployment_address+'/'
	logger.debug("Added / at the end of deployment_address: %s"%(deployment_address))

def writeOnSTDERR(msg):
	sys.stderr.write(msg)

# --- Checks presence of a file or a folder
def checkPresence(file):
	if os.path.exists(file):
		return 0
	else:
		return 1

# --- Opening keychain

def openKeychain(password, keychain):
	cmd_array=(["/usr/bin/security","unlock-keychain", "-p", password, keychain])
	try:
		subprocess.check_call(cmd_array)
	except OSError as e:
		logger.debug("Error in %s, exiting"% " ".join(cmd_array))
		writeToSTDERR("Error, please see the log file")
		sys.exit(1)

	cmd_array=(["/usr/bin/security", "default-keychain","-d","user", "-s", keychain])
	try:
		subprocess.check_call(cmd_array)
	except OSError as e:
		logger.debug("Error in %s, exiting"% " ".join(cmd_array))

# --- Compiling

def compileApp(SDK, project, configuration, target):
	cmd_array=(["/usr/bin/xcodebuild","-sdk",SDK,"-project",project,"-configuration",configuration, "-target", target])
	try:
		subprocess.check_call(cmd_array)
	except OSError as e:
		logger.debug("Error in %s. Exiting"% " ".join(cmd_array)) 
		writeToSTDERR("Error, please see the log file")
		sys.exit(1)
	
# --- Transforming .app into .ipa 
def createIPA(SDK, workspace, configuration, target, DeveloperName, ProvisionningProfilei,targetFolder):
	cmd_array=(["/usr/bin/xcrun","-sdk",GSDK, "PackageApplication", "-v","%s/%s.app"% (APPPath,target),"-o","%s/%s.ipa"%(targetFolder,target),"-sign","%s"%(DeveloperName), "-embed","%s"%(ProvisionningProfile)]) 

	try:
		subprocess.check_call(cmd_array)
	except OSError as e:
		logger.debug("Error in %s. Exiting"% " ".join(cmd_array))
		logger.info(" Error String == %s Error Num == %d"% (e.strerror, e.errno))
		writeToSTDERR("Error, please see the log file")
		sys.exit(1)

def retreiveInfo(targetFolder,target):
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
	xmlfile="/%s/%s.xml"%(targetFolder,target)
	
	# we need to convert Info.plist into a xml file (by default it's a binary plist)

	cmd_array=(["/usr/bin/plutil", "-convert", "xml1", "-o", xmlfile, info])
	subprocess.Popen(cmd_array).wait()
	infoPlistFile = open(xmlfile, 'r')
	app_plist = plistlib.readPlist(infoPlistFile)
	manifestFilename='/%s/manifest.plist'%(targetFolder)

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
	xmlfile="/%s/%s.xml"%(targetFolder,target)
    infoPlistFile = open(xmlfile, 'r')
    app_plist = plistlib.readPlist(infoPlistFile)
    buildNumber = app_plist['CWBuildNumber']
    buildString = str(buildNumber)

	manifestPath="%s%s"%(deployment_address,manifest)
	template_html="""
	<!DOCTYPE html PUBLIC "-//WC3/DTD HTML 1.0 Transitional/EN" "http://www.w3c.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
	<html xmlns="http://www.w3.org/1999/xhtml">
	<head>
	<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
	<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0">
	<title>[BETA_NAME] - Beta Release ([BUILD_NUMBER])</title>
	<style type="text/css">
	body {background:#fff;margin:0;padding:0;font-family:arial,helvetica,sans-serif;text-align:center;padding:10px;color:#333;font-size:16px;}
	#container {width:300px;margin:0 auto;border:2px solid #000;border-radius:15px; box-shadow:4px 4px 4px gray;}
	h1 {margin:0;padding:0;font-size:14px;}
	p {font-size:13px;}
	.link {background:#ecf5ff;border-top:1px solid #fff;border:1px solid #dfebf8;margin-top:.5em;padding:.3em;}
	.link a {text-decoration:none;font-size:15px;display:block;color:#069;}
	
	</style>
	</head>
	<body>
	
	<div id="container">
	
	<h1>Dear testers</h1>
	
	<div class="link"><a href="itms-services://?action=download-manifest&url=[DEPLOYMENT_PATH]">Tap here to install<br />[BETA_NAME] ([BUILD_NUMBER])<br />On Your Device</a></div>
	
	<p><strong>Link didn't work?</strong><br />
	Make sure you're visiting this page on your device, not your computer.</p>
	
	</body>
	</html>
	"""
	TEMPLATE_PLACEHOLDER_NAME = '[BETA_NAME]'
	TEMPLATE_PLACEHOLDER_DEPLOYMENT_PATH = '[DEPLOYMENT_PATH]'
	TEMPLATE_PLACEHOLDER_BUILD = '[BUILD_NUMBER]'
	template_html = string.replace(template_html, TEMPLATE_PLACEHOLDER_NAME, app_name)
	template_html = string.replace(template_html, TEMPLATE_PLACEHOLDER_DEPLOYMENT_PATH, manifestPath)
	template_html = string.replace(template_html, TEMPLATE_PLACEHOLDER_BUILD,buildString)
	os.remove(xmlfile)
	return template_html

def createIndexHTML(targetFolder,target,manifest):
	indexFilename = '/%s/index.html'%(targetFolder)
	manifest=os.path.basename(manifest)
	indexFile = open(indexFilename, 'w')
	indexFile.write(fillHTML(target,manifest))
	return indexFilename

def createTargetFolder(folder):
	try:
		subprocess.call(["/bin/mkdir", folder])
	except OSError as e:
		if os.path.exists(folder):
			logger.info("%s folder already exist, Exiting")
			logger.debug("ErrorString == %s ErrorNum == %d"% (e.strerror,e.errno))
			pass
		else:
			raise Exception("Error in creating %s folder"% (folder))
			writeToSTDERR("Error, please see the log file")
			sys.exit(1)

def distribution(server, user, password,distantFolder,sourceFolder):
	
	for each in os.listdir(sourceFolder):
		path="%s/%s"%(sourceFolder,each)
		cmd_array=(["/usr/bin/scp",path,"%s@%s:%s"%(user,server,distantFolder)]) 	
		logger.debug("%s"% " ".join(cmd_array))
		try:
			subprocess.check_call(cmd_array)
		except OSError as e:
			logger.debug("Error in %s. Exiting"% " ".join(cmd_array)) 
			logger.debug("ErrorString == %s ErrorNum == %d"% (e.strerror,e.errno))
			writeToSTDERR("Error during distribution, please look at the log file")
 
def gitClone(gitRepository, projectPath):
	logger.debug("Clonning %s into % s"%(gitRepository, projectPath))
	git.Repo.clone_from(gitRepository,projectPath)

def gitPull(projectPath):
	logger.debug("Pull repository into %s"%(projectPath))
	os.chdir(projectPath)
	repo = git.Repo(projectPath)
	repo.remotes.origin.pull()

def increaseBuildNumber(project,subdir,plistFile):
	cmd_array=["/usr/libexec/PlistBuddy", "-c", "Print CWBuildNumber", "%s/%s/%s"%(project,subdir,plistFile)]
	s = subprocess.Popen(cmd_array, stdout=subprocess.PIPE)
	ret = s.stdout.readline()
	buildNumber = int(ret)
	buildNumber+=1

	cmd_array=["/usr/libexec/PlistBuddy", "-c", "Set :CWBuildNumber %s"%(buildNumber),"%s/%s/%s"%(project,subdir,plistFile)]
	try:
		subprocess.check_call(cmd_array)
	except OSError as e:
		logger.debug("Error in %s. Exiting"% " ".join(cmd_array)) 
		logger.debug("ErrorString == %s ErrorNum == %d"% (e.strerror,e.errno))
		writeToSTDERR("Error during increase BuildNumber")

# --- Other variables
logger.debug("project == %s"%(project))
if 'xcodeproj' not in project:
	logger.info("Project file path must end with xcodeproj")
	writeOnSTDERR("Project file path must end with xcodeproj")
	sys.exit(1)

# -- GSDK is SDK without version (iphoneos5.0 -> iphoneos)
GSDK = SDK[:-3]
logger.debug("GDSK == %s"%(GSDK))
# -- APPPath is the Path to the generated APP 
APPPath="%s/build/%s-%s"%(workspace,configuration,GSDK)
logger.debug("APPPath == %s"%(APPPath))

# -- timestamp is used to create de unique target Folder
timestamp = int(time.time())
targetFolder="/tmp/%s-%d"%(target,timestamp)
logger.debug("targetFolder == %s"%(targetFolder))

logger.debug("project == %s"%(project))
logger.debug("workspace == %s"%(workspace))

# -- ProjectPath
projectPath,projectName = os.path.split(project)

# --- Check presence of the keychain and the project
if checkPresence(keychain) != 0:
	logger.debug("Keychain %s not found"%(keychain))
	writeOnSTDERR("Keychain %s not found"%(keychain))
	sys.exit(1)
	
if checkPresence(projectPath) == 1:
	logger.debug("%s does not exist"%(projectPath))
	subprocess.call(["/bin/mkdir",projectPath])

if checkPresence("%s/.git"%(projectPath)) == 1:
	logger.debug("No .git folder in %s"%(projectPath))
	gitClone(gitRepository,projectPath)
else:
	logger.debug("Already a clone, making a pull")
	gitPull(project)

# --- Openning the keychain
openKeychain(password, keychain)

# --- Create the target folder in /tmp
createTargetFolder(targetFolder)

# --- Increase BuildNumber
increaseBuildNumber(projectPath,"PillStock","PillStock-Info.plist")

# --- Compile to .app
compileApp(SDK, project, configuration, target)

# --- Transforme the .app into .ipa (in targetFolder)
createIPA(SDK, workspace, configuration, target, DeveloperName, ProvisionningProfile,targetFolder)

# --- Extract Info.plsit form .ipa file
info=retreiveInfo(targetFolder,target)

# --- Create Manifest.plist
manifest=createManifest(info,target,targetFolder,deployment_address)

# --- Create index.hml file
htmlFile=createIndexHTML(targetFolder,target,manifest)

# --- Send files on distribution machine
distribution(remoteHost, username, password, remoteFolder, targetFolder)

