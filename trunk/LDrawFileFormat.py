import shutil  # for file copy / rename
import os      # for path creation

import Drawables  # Box, Point
import povray     # Build images from povray files
import l3p        # Build povray from DAT files
import config     # For user path info

Comment = '0'
PartCommand = '1'
LineCommand = '2'
TriangleCommand = '3'
QuadCommand = '4'
ConditionalLineCommand = '5'

RotStepCommand = 'ROTSTEP'
StepCommand = 'STEP'
FileCommand = 'FILE'
ClearCommand = 'CLEAR'
PauseCommand = 'PAUSE'
SaveCommand = 'SAVE'
GhostCommand = 'GHOST'
BufferCommand = 'BUFEXCHG'
BFCCommand = 'BFC'

BufferStore = 'STORE'
BufferRetrieve = 'RETRIEVE'

LPubCommand = 'LPUB'
LicCommand = '!LIC'
LicInitialized = 'Initialized'
CSICommand  = 'CSI'
PLICommand  = 'PLI'
PageCommand = 'PAGE'
PLIItemCommand  = 'PLII'
BEGINCommand  = 'BEGIN'
ENDCommand  = 'END'
IGNCommand  = 'IGN'

def LDToOGLMatrix(matrix):
	m = [float(x) for x in matrix]
	return [m[3], m[6], m[9], 0.0, m[4], m[7], m[10], 0.0, m[5], m[8], m[11], 0.0, m[0], m[1], m[2], 1.0]

def isValidCommentLine(line):
	return (len(line) > 2) and (line[1] == Comment)

def isValidTriangleLine(line):
	return (len(line) == 12) and (line[1] == TriangleCommand)

def lineToTriangle(line):
	d = {}
	d['color'] = float(line[2])
	d['points'] = [float(x) for x in line[3:]]
	return d

def isValidQuadLine(line):
	return (len(line) == 15) and (line[1] == QuadCommand)

def lineToQuad(line):
	d = {}
	d['color'] = float(line[2])
	d['points'] = [float(x) for x in line[3:]]
	return d

def isValidFileLine(line):
	return (len(line) > 2) and (line[1] == Comment) and (line[2] == FileCommand)

def isValidStepLine(line):
	return (len(line) > 2) and (line[1] == Comment) and (line[2] == StepCommand)

def isValidRotStepLine(line):
	return (len(line) > 3) and (line[1] == Comment) and (line[2] == RotStepCommand)

def lineToRotStep(line):
	d = {}
	if len(line) < 6:
		d['state'] = ENDCommand
	else:
		d['point'] = Drawables.Point3D(float(line[3]), float(line[4]), float(line[5]))
		if len(line) == 7:
			d['state'] = line[6]
		else:
			d['state'] = 'REL'
	return d
	
def isValidPartLine(line):
	return (len(line) > 15) and (line[1] == PartCommand)

def lineToPart(line):
	return {'filename': line[15],
			'color': int(line[2]),
			'matrix': LDToOGLMatrix(line[3:15]),
			'ghost': False}

def isValidGhostLine(line):
	return (len(line) > 17) and (line[1] == Comment) and (line[2] == GhostCommand) and (line[3] == PartCommand)

def ghostLineToPartLine(line):
	return line[:1] + line[3:]

def lineToGhostPart(line):
	d = lineToPart(line[2:])
	d['ghost'] = True
	return d

def isValidBufferLine(line):
	return (len(line) > 4) and (line[1] == Comment) and (line[2] == BufferCommand)

def lineToBuffer(line):
	return {'buffer': line[3], 'state': line[4]}

def isValidBFCLine(line):
	# TODO: implement all BFC options
	return (len(line) > 3) and (line[1] == Comment) and (line[2] == BFCCommand)

def lineToBFC(line):
	# TODO: implement all BFC options
	return {'command': line[3]}

def isValidLPubLine(line):
	return (len(line) > 3) and (line[1] == Comment) and (line[2] == LPubCommand)

def isValidLPubPLILine(line):
	return isValidLPubLine(line) and (len(line) > 4) and (line[3] == PLICommand)

def lineToLPubPLIState(line):
	if line[4] == BEGINCommand:
		return True
	return False

def isValidLPubSizeLine(line):
	return isValidLPubLine(line) and (len(line) > 6) and (line[3] == PageCommand)

def lineToLPubSize(line):
	return (int(line[5]), int(line[6]))

def isValidLicLine(line):
	return (len(line) > 3) and (line[1] == Comment) and (line[2] == LicCommand)

def isValidLicHeader(line):
	return isValidLicLine(line) and (len(line) == 4) and (line[3] == LicInitialized)

def isValidCSILine(line):
	return isValidLicLine(line) and (len(line) > 9) and (line[3] == CSICommand)

def lineToCSI(line):
	# [index, Comment, LicCommand, CSICommand, self.box.x, self.box.y, self.box.width, self.box.height, self.centerOffset.x, self.centerOffset.y]
	return {'box': Drawables.Box(float(line[4]), float(line[5]), float(line[6]), float(line[7])),
			'center': Drawables.Point(float(line[8]), float(line[9]))}

def isValidPLILine(line):
	return isValidLicLine(line) and (len(line) > 14) and (line[3] == PLICommand)

def lineToPLI(line):
	# [index, Comment, LicCommand, PLICommand, self.box.x, self.box.y, self.box.width, self.box.height,
	#  self.qtyMultiplierChar, self.qtyLabelFont.size, self.qtyLabelFont.face,
	#  self.step.stepNumberRefPt.x, self.stepNumberRefPt.y,
	#  self.step.stepNumberFont.size, self.step.stepNumberFont.face]
	return {'box': Drawables.Box(float(line[4]), float(line[5]), float(line[6]), float(line[7])),
			'qtyLabel': line[8],
			'qtyFont': Drawables.Font(float(line[9]), line[10]),
			'stepLabelPt': Drawables.Point(float(line[11]), float(line[12])),
			'stepLabelFont': Drawables.Font(float(line[13]), line[14])}

def isValidPLIItemLine(line):
	return isValidLicLine(line) and (len(line) > 11) and (line[3] == PLIItemCommand)

def lineToPLIItem(line):
	# [index, Comment, LicCommand, PLIItemCommand, filename, item.count, item.corner.x, item.corner.y, item.labelCorner.x, item.labelCorner.y, item.xBearing, color]
	return {'filename': line[4],
			'count': int(line[5]),
			'corner': Drawables.Point(float(line[6]), float(line[7])),
			'labelCorner': Drawables.Point(float(line[8]), float(line[9])),
			'xBearing'   : float(line[10]),
			'color': int(line[11])}

def isValidPageLine(line):
	return isValidLicLine(line) and (len(line) > 3) and (line[3] == PageCommand)

class LDrawFile:
	def __init__(self, filename):
		
		self.path = config.LDrawPath  # path where filename was found
		self.filename = filename      # filename, like 3057.dat
		self.name = ""                # coloquial name, like 2 x 2 brick
		self.isPrimitive = False      # Anything in the 'P' directory
		
		self.fileArray = []
		self.subModelArray = {}
		
		self._loadFileArray()
		self._findSubModelsInFile()
		
		cwd = os.getcwd()
		self.datPath = os.path.join(cwd, 'DATs')
		if not os.path.isdir(self.datPath):
			os.mkdir(self.datPath)   # Create DAT directory if needed
		
		self.povPath = os.path.join(cwd, 'POVs')
		if not os.path.isdir(self.povPath):
			os.mkdir(self.povPath)   # Create POV directory if needed
		
		self.pngPath = os.path.join(cwd, 'PNGs')
		if not os.path.isdir(self.pngPath):
			os.mkdir(self.pngPath)   # Create PNG directory if needed

	def addLicHeader(self):
		
		for i, line in enumerate(self.fileArray):
			
			if isValidLicHeader(line):
				return  # Already initialized this file
			
			if isValidLicLine(line) or isValidStepLine(line) or isValidPartLine(line) or isValidGhostLine(line) or isValidBufferLine(line) or isValidLPubPLILine(line):  
				break  # We've hit the first real line in the file - insert header just before this
		
		self.insertLine(i, [Comment, LicCommand, LicInitialized])

	def addInitialSteps(self):
		
		lines = []
		currentFileLine = False
		firstLine = -1
		
		for line in self.fileArray:
			
			if isValidLicHeader(line):
				return  # Already initialized this file
			
			if isValidFileLine(line):
				currentFileLine = True
			
			if isValidStepLine(line):   # Already have initial step - nothing to do here
				currentFileLine = False
			
			if isValidPartLine(line) or isValidGhostLine(line) or isValidBufferLine(line) or isValidLPubPLILine(line) or isValidCSILine(line):
				if firstLine == -1:
					firstLine = line[0]
				if currentFileLine:
					lines.append(line)
					currentFileLine = False
		
		if lines == []:
			# Found no FILE lines, so insert step right before first real line
			lines.append(self.fileArray[max(0, firstLine-1)])
		
		for line in lines:
			self.insertLine(line[0] - 1, [Comment, StepCommand])

	def addDefaultPages(self):
		
		lines = []
		for line in self.fileArray:
			
			if isValidLicHeader(line):
				return  # Already initialized this file
			
			if isValidPageLine(line):
				return  # Already have pages in file - nothing to do here
			
			if isValidStepLine(line):
				lines.append(line)
		
		for line in lines:
			self.insertLine(line[0] - 1, [Comment, LicCommand, PageCommand])
	
	def insertLine(self, index, line):
		"""
		Insert the specified line into the file array at the specified index (0-based).
		line is expected to be an array of various types, making up the overall LDraw line to be added.
		Do not prepend the line number - line should start with one of the LDraw commands listed above.
		line will be modified to include the appropriate line index, and all entries converted to strings.
		"""
		
		# Convert line entries to strings, and prepend line number to the line command, as the file array expects
		fileLine = [str(x) for x in line]
		fileLine.insert(0, index + 1)
		
		# Insert the new line
		self.fileArray.insert(index, fileLine)
		
		# Adjust all subsequent line numbers
		for line in self.fileArray[index + 1:]:
			line[0] += 1
		
		# Adjust all line numbers in the subModel array too, if we inserted the line before their indices
		# self.subModelArray = {"filename": [startline, endline]}
		for line in self.subModelArray.values():
			if line[0] >= index:
				line[0] += 1
			if line[1] >= index:
				line[1] += 1
		
		return fileLine

	def saveFile(self, filename = None):
		
		if filename is None:
			filename = self.filename
		filename = os.path.join(self.path, filename)
		
		print "*** Saving: %s ***" % (filename)
		
		# First, make a backup copy of the existing file
		shutil.move(filename, filename + ".bak")
		
		# Dump the current file array to the chosen file
		f = open(filename, 'w')
		for line in self.fileArray:
			f.write(' '.join(line[1:]) + '\n')
		f.close()

	def _loadFileArray(self):
		
		try:
			f = file(os.path.join(config.LDrawPath, 'MODELS', self.filename))
			self.path = os.path.join(self.path, 'MODELS')
		except IOError:
			try:
				f = file(os.path.join(config.LDrawPath, 'PARTS', self.filename))
				self.path = os.path.join(self.path, 'PARTS')
				if (self.filename[:2] == 's\\'):
					self.isPrimitive = True
			except IOError:
				f = file(os.path.join(config.LDrawPath, 'P', self.filename))
				self.path = os.path.join(self.path, 'P')
				self.isPrimitive = True
		
		# copy the file into an internal array, for easier access
		i = 1
		for l in f:
			self.fileArray.append([i] + l.split())
			i += 1
		f.close()
		
		self.name = ' '.join(self.fileArray[0][2:])

	def _findSubModelsInFile(self):
		
		# Loop through the file array searching for sub model FILE declarations
		subModels = []  # subModels[0] = (filename, start line number)
		for i, l in enumerate(self.fileArray):
			if isValidFileLine(l):
				subModels.append((l[3], i))
		
		if len(subModels) < 1:
			return  # No subModels in file - we're done
		
		# Fixup subModel array by calculating the ending line number from the file
		for i in range(0, len(subModels)-1):
			subModels[i] = (subModels[i][0], [subModels[i][1], subModels[i+1][1]])
		
		# Last subModel is special case: its ending line is end of file array
		subModels[-1] = (subModels[-1][0], [subModels[-1][1], len(self.fileArray)])
		
		# self.subModelArray = {"filename": [startline, endline]}
		self.subModelArray = dict(subModels)

	def writeLinesToDat(self, filename, start, end):
		
		filename = os.path.join(self.datPath, filename)
		if os.path.isfile(filename):
			# TODO: Ensure this DAT is up to date wrt the main model
			return   # DAT already exists - nothing to do
		
		print "Creating dat for: %s, line %d to %d" % (filename, start, end)
		f = open(filename, 'w')
		for line in self.fileArray[start:end]:
			f.write(' '.join(line[1:]) + '\n')
		f.close()
		
		return filename

	def splitOneStepDat(self, stepLine, stepNumber, filename, start = 0, end = -1):
		
		if end == -1:
			end = len(self.fileArray)
		
		rawFilename = os.path.splitext(os.path.basename(filename))[0]
		datFilename = os.path.join(self.datPath, '%s_step_%d.dat' % (rawFilename, stepNumber))
		
		if os.path.isfile(datFilename):
			return datFilename  # dat file already exists - no need to recreate
		
		fileLines = []
		inCurrentStep = False
		for line in self.fileArray[start:end]:
			if line == stepLine:
				inCurrentStep = True
			elif isValidStepLine(line) and inCurrentStep:
				break
			fileLines.append(line)
		
		bufStack = ''
		lineDict = {}
		for i, line in enumerate(fileLines):
			
			if lineDict.has_key(bufStack):
				lineDict[bufStack].append(i)
			else:
				lineDict[bufStack] = [i]
			
			if isValidBufferLine(line):
				buffer, state = lineToBuffer(line).values()
				
				if state == BufferStore:
					bufStack = bufStack + buffer
					
				elif state == BufferRetrieve:
					if lineDict.has_key(bufStack):
						lineDict.pop(bufStack)
					if bufStack[-1] == buffer:
						bufStack = bufStack[:-1]
					else:
						print "Buffer Exchange Error.  Last stored buffer: ", bufStack[-1], " but trying to retrieve buffer: ", buffer
		
		newLines = []
		for lines in lineDict.values():
			for i in lines:
				line = fileLines[i]
				if isValidGhostLine(line):
					newLines.append(ghostLineToPartLine(line))
				elif (not isValidCommentLine(line)) or (len(line) < 1):
					newLines.append(line)
		
		f = open(datFilename, 'w')
		for line in newLines:
			f.write(' '.join(line[1:]) + '\n')
		f.close()
		return datFilename

	def createPov(self, width, height, datFile, camera, offset, color = None):
		
		if datFile is None:
			datFile = os.path.join(self.path, self.filename)
		
		rawFilename = os.path.splitext(os.path.basename(datFile))[0]
		
		if color:
			povFile = "%s_%d.pov" % (os.path.join(self.povPath, rawFilename), color)
		else:
			povFile = "%s.pov" % (os.path.join(self.povPath, rawFilename))
		
		if not os.path.isfile(povFile):
			# Create a pov from the specified dat via l3p
			l3pCommand = l3p.getDefaultCommand()
			l3pCommand['inFile'] = datFile
			l3pCommand['outFile'] = povFile
			if color:
				l3pCommand['color'] = color
			l3p.runCommand(l3pCommand)
		
		# Convert the generated pov into a nice png
		pngFile = os.path.join(self.pngPath, rawFilename)
		if color:
			pngFile = "%s_%d.png" % (pngFile, color)
		else:
			pngFile = "%s.png" % (pngFile)
		
		if not os.path.isfile(pngFile):
			povray.fixPovFile(povFile, width, height, offset, camera)
			povCommand = povray.getDefaultCommand()
			povCommand['inFile'] = povFile
			povCommand['outFile'] = pngFile
			povCommand['width'] = width
			povCommand['height'] = height
			povray.runCommand(povCommand)
		
		return pngFile
