from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
import dropbox
import time
import sys
import re

class Desire2Download:

	def __init__(self, username, password, overwrite, ignoreFiles, ignoreCourses, path) :
		self.username = username
		self.password = password
		self.overwrite = overwrite
		self.ignoreFiles = ignoreFiles
		self.ignoreCourses = ignoreCourses
		self.path = path
		self.url = "https://learn.uwaterloo.ca"
		self.filesInCurrentDirectory = []
		# list of browsers these are URLs
		# URL possibilities: [{home}, {courses}, {grades, announcements, content}, {if content: }]
		self.pageHistory = []
		# list of files.
		self.fileHistory = []
		# True if grade page has been already loaded in browser. Otherwise False.
		self.gradeLoaded = False
		# True if content page has been already loaded in browser. Otherwise False.
		self.contentLoaded = False
		# Dropbox instance. If already authenticated it will hold an instance. Otherwise None.
		self.getDropboxAuth()

	def getDropboxAuth(self) :
		try :
			file = open("../d2d.auth", "r")
			self.dbx = dropbox.Dropbox(file.read())
		except Exception :
			self.dbx = None

	def login(self) :
		xpaths = { 'usernameTxtBox' : "//input[@name='username']",
				   'passwordTxtBox' : "//input[@name='password']",
				   'submitButton' : "//input[@name='submit']"
				 }
		try:
			browser = webdriver.PhantomJS(executable_path = self.path)
			# Set fake browser size before doing get. This is to avoid 'Element is not currently visible and may not be manipulated' exception
			browser.set_window_size(1124, 850)
			browser.get(self.url)

			# Output Message
			print("Logging in to " + self.url + "...")

			# Clear the username textbox if already allowed by "Remember me".
			browser.find_element_by_xpath(xpaths['usernameTxtBox']).clear()

			# Write username in Username textbox
			browser.find_element_by_xpath(xpaths['usernameTxtBox']).send_keys(self.username)

			# Clear password textbox if already allowed by "Remember me"
			browser.find_element_by_xpath(xpaths['passwordTxtBox']).clear()

			# Write password in Password textbox
			browser.find_element_by_xpath(xpaths['passwordTxtBox']).send_keys(self.password)

			# Click login button
			browser.find_element_by_xpath(xpaths['submitButton']).click()

			# Check if its login credentials is correct
			if browser.current_url != self.url + "/d2l/home" :
				print("Error: Invalid username or password")
				sys.exit(2)

			# Output Message
			print("Logged in.")

			self.browser = browser
			self.pageHistory.append(self.browser.current_url)

		except KeyboardInterrupt:
			browser.close()

	def getContent(self) :
		# This is the element which lists all the courses 
		# (Can't use BeautifulSoup or MechanicalSoup due to new learn updates)
		courses = "//a[@class='d2l-image-tile-base-link style-scope d2l-image-tile-base']"

		# Increasing time will guarantee javascript loading but 5 sec should be enough in most cases.
		time.sleep(1)
		self.load(courses, 5)

		courseElements = self.browser.find_elements_by_xpath(courses)
		courseInfoDict = {}

		for course in courseElements:
			# print('Adding ' + course.text + ' and ' + course.get_attribute("href"))
			courseInfoDict[course.text.strip()] = course.get_attribute("href")

		self.courseInfoDict = courseInfoDict

	# Method to wait until condition is loaded
	def load(self, xpath, timeout) :
		try:
			element_present = EC.presence_of_element_located((By.XPATH, xpath))
			WebDriverWait(self.browser, timeout).until(element_present)
			time.sleep(1)
		except TimeoutException:
   			print("Timed out waiting for page to load")

   	# Method to find out URLs for announcement, grades and content
   	# Returns KVP in the form of {[grades, url], [content, url]}
	def specificCourseHome(self) :
		toRet = {}
		xpath = "//a[@class='d2l-navigation-s-link']"	
		self.load(xpath, 5)

		elements = self.browser.find_elements_by_xpath(xpath)

		for element in elements :
				text = element.text.strip()
				if text == "Grades" or text == "Content" :
					toRet[text] = element.get_attribute("href")

		self.filesInCurrentDirectory = []
		for key in toRet :
			self.filesInCurrentDirectory.append(key)
		self.gradeContent = toRet

	# This method is basically called when app logged into learn and lists all the courses and commands available.
	# This is only called once.
	def getCourseHome(self) :
		self.removeIgnoreCourses()

		toPrint = self.getCommands()

		# print for init.
		toPrint += "\nList of all the courses:\n"

		# for each course, open the URI.
		for courseName in self.courseInfoDict :
			toPrint += "- " + courseName + "\n"
			self.filesInCurrentDirectory.append(courseName)
		self.fileHistory.append(self.filesInCurrentDirectory)
		print(toPrint)

	# This method is basically help command.
	def getCommands(self) :
		toRet = "\nList of available commands:\n"

		toRet += "- h: help\n"
		toRet += "- q: quit\n"
		toRet += "- ls: list information about files in current directory\n"
		toRet += "- cd: change directory\n"
		toRet += "- d2d: downloads specified file and drops it to your dropbox\n"
		toRet += "       If file is not specified then everything under the current directory\n"
		toRet += "       will be downloaded and dropped into your dropbox\n"

		return toRet

	# Method to print files in current directory
	def lsCommand(self) :
		toPrint = "\nFiles in current directory:\n"
		for file in self.filesInCurrentDirectory :
			toPrint += "- " + file + "\n"
		print(toPrint)

	# Method to change directory.
	def cdCommand(self, commands) :
		directory = ""
		for c in commands :
			directory += " " + c
		directory = directory.strip()

		size = len(self.pageHistory)

		if directory == ".." :
			if size == 1 :
				print("This is the home directory")
			else :	
				self.browser.get(self.pageHistory[size - 2])
				self.filesInCurrentDirectory = self.fileHistory[size - 2]
				self.pageHistory.pop()
				self.fileHistory.pop()
				# Debugging purpose
				print(self.pageHistory[size - 2])
		elif directory in self.filesInCurrentDirectory :
			link = None
			if size == 1 :
				link = self.courseInfoDict[directory]
				self.browser.get(link)
				#Debugging purpose
				# print(self.browser.current_url)
				self.specificCourseHome()
			if size == 2 :
				link = self.gradeContent[directory]
				self.filesInCurrentDirectory = []
				self.browser.get(link)
				if directory == "Grades" :
					self.getFilesInCurrentDirectoryGrades()
				if directory == "Content" :
					self.getFilesInCurrentDirectoryContent()
			self.pageHistory.append(link)
			self.fileHistory.append(self.filesInCurrentDirectory)
			# Debugging purpose
			print(link)
		else :
			print(directory + " does not exist")


	def getFilesInCurrentDirectoryGrades(self) :
		timeSec = 3
		if self.gradeLoaded :
			timeSec = 1
		time.sleep(timeSec)
		self.gradeLoaded = True
		gradesTableXpath = "//div[@class='d2l-grid-container']"
		tableRowXpath = "//tr"
		tableColTextXpath = "//label"

		tableRows = self.browser.find_elements_by_xpath(tableRowXpath)

		if len(tableRows) == 1 : 
			return

		print("\n-------------------------------------------------")
		i = 0
		for tableRow in tableRows :
			if i > 0 :
				print(tableRow.text)
				print("-------------------------------------------------")
			i = i + 1

	def getFilesInCurrentDirectoryContent(self) :
		timeSec = 5
		if self.contentLoaded :
			timeSec = 2
		time.sleep(timeSec)
		self.contentLoaded = True
		listXpath = "//li"
		tableOfContentXpath = "//ul//ul//li[contains(@class, 'd2l-datalist-item') and contains(@class ,'d2l-datalist-simpleitem')]"
		dirList = self.browser.find_elements_by_xpath(listXpath)

		for directory in dirList :
			if directory.text.startswith("Table of Contents") :
				directory.click()
				time.sleep(timeSec)
				tableOfContent = self.browser.find_elements_by_xpath(tableOfContentXpath)
				for file in tableOfContent :
					fileName = file.text.strip()
					if fileName != "" :
						self.filesInCurrentDirectory.append(fileName.splitlines()[0])

	def getInput(self) :
		command = ""
		while command != "q" :
			command = input(">>> ").strip()
			self.processInput(command)

	def processInput(self, commands) :
		command = re.split(r'\s{1,}', commands)
		if command[0] == "ls":
			self.lsCommand()
		elif command[0] == "cd":
			self.cdCommand(command[1:])
		elif command[0] == "d2d":
			print("d2d")
			dbx = dropbox.Dropbox("eyfYhpO4qDAAAAAAAAAACq85M49Hy932LpZLlAFC5csGELUz8c-3FkargQh743WJ")
			self.uploadToDropbox()
		elif command[0] == "h":
			print(self.getCommands())
		elif command[0] == "q":
			#do nothing
			print("Exiting...")
		else :
			print("Unknown command. Please type h to see list of commands available")

	def uploadToDropbox(self) :
		# look at the api to finish this.
		self.dbx.files_upload()

	def removeIgnoreCourses(self) :
		for ignoreCourseRegex in self.ignoreCourses :
			listOfKeysToRemove = []
			# Iterate through course names and add any courses that need to be ignored
			for courseNames in self.courseInfoDict :
				if (ignoreCourseRegex.search(courseNames)) :
					listOfKeysToRemove.append(courseNames)

			# Now actually delete those courses in the dictionar y
			for keyToBeRemoved in listOfKeysToRemove :
				del self.courseInfoDict[keyToBeRemoved]


	def tearDown(self) :
		self.browser.close()
		