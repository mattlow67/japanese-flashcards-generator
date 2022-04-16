
from jamdict import Jamdict
import pykakasi
import fugashi
import sys
import re
import json
import requests
from bs4 import BeautifulSoup

jam = Jamdict()
kakasi = pykakasi.kakasi()
tagger = fugashi.Tagger()

infilepath = f'words/{sys.argv[1]}'
outfilepath = 'output.tsv'
logfilepath = 'log.txt'
hilite = 'term'
THRESHOLD = 0.35

hitexcept = {'に','は','て','を','が','だ','た','で','も','です','か','から','居る','無い' \
			'・','「','」','）','（','！','や','。','？','っ','…','、','\''}



def iskanji(chr):
    chrhex = int(hex(ord(chr)),16)
    
    if chrhex > 0x4e00 and chrhex < 0x9faf:
        return True
        
    return False

	
def getkana(result):
	
	return(repr(result.entries[0].kana_forms[0]))
	
	
def haskanji(word):
	hkanji = False
	
	for c in word:
		if iskanji(c):
			hkanji = True
	
	return hkanji
	
	
def isverbadj(term):
	result = jam.lookup(term)
	
	if 'dan verb' in repr(result.entries[0].senses) \
		or 'adjective' in repr(result.entries[0].senses):
		return True
		
	return False			


def getdef(result):
	
	definition = ''
	dentry = result.entries[0] #first dictionary entry

	defs = repr(dentry.senses[0]).split(' ((')[0]
	defs = defs.split('/')
	
	for dftn in defs:
		definition = definition + f'{dftn}, '
		
	#remove last apostraphe and whitespace
	definition = definition[:-2]
	
	return(definition)
	

def getkanji(result, term):
	#each kanji has one line
	kanjidefs = []

	for entry in result.chars:
		#kanji:stroke_order:meanings,
		eentry = repr(entry).split(':')
		
		if eentry[0] in term:	#whether kanji is in term
			#get no more than three defs per kanji
			emidx = 0
			emeanings = ''
			for defi in eentry[2].split(','):
				if emidx > 2:
					break
				emeanings = emeanings+defi+', '
				emidx += 1
			#remove last apostraphe and whitespace
			emeanings = emeanings[:-2]		

			kanjidefs.append(f'{eentry[0]}: {emeanings}')
			
	#remove trailing <br>
	#kanjidefs = kanjidefs[:-4]

	return kanjidefs
	
	
def getsyns(result):
	#get results for first defintion of term
	sterm = getdef(result).split(', ')[0]
	sresult = jam.lookup(sterm)
	synslist = []
	synidx = 0
	
	for entry in sresult.entries:
		#limit num of synonyms to 5
		if synidx > 4:
			break
		
		thissyn = repr(entry.kanji_forms[0]) if entry.kanji_forms else ''
		thissyn = thissyn +'['+repr(entry.kana_forms[0])+']: '
		
		thissyndefs = repr(entry.senses[0]).split(' ((')[0]
		thissyndefs = thissyndefs.split('/')
		
		syndefidx = 0
		for dftn in thissyndefs:
			if syndefidx > 2:
				break
			thissyn = thissyn + f'{dftn}, '
			syndefidx += 1
			
		#remove last apostraphe and whitespace, add html
		thissyn = thissyn[:-2]
		
		synslist.append(thissyn)
		synidx += 1		
	
	return synslist
	

def getscoredsents(sentlist):
	sents = sentlist
	wordset = set()
	scoredsents = []
	
	for line in sents:
		words = tagger(line)
		hits = 0
	
		for word in words:
			if word.feature.lemma in wordset and \
			word.feature.lemma not in hitexcept:
				hits += 1
			#add current line's lemmas to set
			wordset.add(word.feature.lemma)
			
		score = hits / len(words)
		
		if score < THRESHOLD:
			scoredsents.append(line)
			
	return scoredsents		
		

def getfurisents(scoredlist, term):
	sents = scoredlist[:10]
	furisentslist = []
	
	if isverbadj(term):
		sterm = term[:-1]
	else:
		sterm = term
		
	sregex = ''
	if haskanji(sterm):
		for c in sterm:
			c += '.*'
			sregex += c
		sregex += '?]'
	else:
		sregex = sterm
	
	idx = 1
	
	#add furigana to sentence
	for line in sents:
		result = kakasi.convert(line)
		line2write = ''
		
		for item in result:
			if haskanji(item['orig']):
				term2write = ' '+item['orig']+'['+item['hira']+']'
			else:
				term2write = item['orig']
				
			line2write += term2write
		
		#remove whitespace at beginning if first lemma is kanji
		line2write = line2write.strip()
		#add html tags to term
		#get found string from regex search
		hreplace = re.search(sregex, line2write)
		
		#exception because hreplace sometimes finds no results
		if hreplace:
			hreplace = hreplace.group()
			#regex requires escape characters
			treplace = re.escape(hreplace)
			line2write = re.sub(treplace,f'<div class="{hilite}">{hreplace}</div>',line2write)
			
		furisentslist.append(f'{idx}. {line2write}')
		idx += 1
		
	return furisentslist
	
	
def getsentences(term, database):
	if database == 1:
		n = '11' #yourei.jp starts indexing at '1'
		url = f"https://yourei.jp/{term}?start=1&n={n}"
		header = {'User-Agent':'Mozilla/5.0'}
		page = requests.get(url, headers=header)
		
		soup = BeautifulSoup(page.text, "html.parser")
		results = soup.find_all("span", class_="the-sentence")
		
		sentlist = []
		for result in results:
			rst = str(result)
			rst = re.sub('<rt>.*?</rt>', '', rst)
			rst = re.sub('<.*?>', '', rst)
			sentlist.append(rst)
			
		sentlist = getfurisents(sentlist, term)	
		
	else:
		sentlist = []
		
	return sentlist
		


def main():

	#specify where to get sentences
	print('Source of sentences?')
	print('1. yourei.jp')
	
	#'source' is origin of term
	#'database' is where sentences are collected
	database = input() #input defaults to string
	while database != '1':
		print('Invalid input.')
		database = input()
		
	database = int(database)

	#start after line with '***'
	infilestart = open(infilepath, 'r', encoding='utf-8')
	findstart = 1
	startidx = 0
	startfound = False
	
	for line in infilestart:
		if '***' in line:
			startfound = True
			startidx = findstart
		findstart += 1
		
	infilestart.close()
	

	with open(infilepath, 'r', encoding='utf-8') as infile, \
		open(outfilepath, 'w', encoding='utf-8') as outfile, \
		open(logfilepath, 'w', encoding='utf-8') as logfile:
		
		#jump ahead to last '***'
		if startfound:
			print(f'continuing at line {startidx}.')
			
			stidx = 1
			for line in infile:
				if stidx == startidx:
					break
				stidx += 1
		else:
			print('starting at first line.')	
		
		
		source = ''	#persist source if it doesn't change

		for line in infile:		
			linesplit = [ls.strip() for ls in line.split('\t')]			
			term = linesplit[0]
			
			#skip if no term present
			if not term:
				continue
			
			result = jam.lookup(term)
			
			#update status on console
			print(term)
			
			if len(result.entries) == 0:
				print(f'Cannot find {term}')
				continue
			
			kana = getkana(result)
			excerpt = linesplit[1]			
			source = linesplit[2] if linesplit[2] != '' else source			
			definition = getdef(result)
			kanji = getkanji(result, term)
			synonyms = getsyns(result)
			sentences = getsentences(term, database)
			
			nt = '\t'	#diagnoses writing issues
			
			#write to anki card format			
			#outfile.write(f'{term}{nt}{kana}{nt}{definition}{nt}')
			outfile.write(f'{term}{nt}')
			if haskanji(term):
				outfile.write(f'{kana}{nt}')
			else:
				outfile.write(nt)
			outfile.write(f'{definition}{nt}')
			
			if kanji:
				for k in kanji[:-1]:
					outfile.write(f'{k}<br>')
				outfile.write(f'{kanji[-1]}{nt}')
			else:
				outfile.write(nt)
			
			if synonyms:
				for s in synonyms[:-1]:
					outfile.write(f'{s}<br>')
				outfile.write(f'{synonyms[-1]}{nt}')
			else:
				outfile.write(nt)
				
			outfile.write(f'{excerpt}{nt}{source}{nt}')
			
			if sentences:
				for se in sentences[:-1]:
					outfile.write(f'{se}<br>')
				outfile.write(f'{sentences[-1]}')
			else:
				outfile.write(nt)
				
			outfile.write('\n')
			
			
			#write to log file
			logfile.write(f'{term}\n{kana}\n{definition}\n')
			
			if kanji:
				for k in kanji[:-1]:
					logfile.write(f'{k}\n')
				logfile.write(f'{kanji[-1]}\n')
			else:
				logfile.write('-no kanji-\n')
			
			if synonyms:
				for s in synonyms[:-1]:
					logfile.write(f'{s}\n')
				logfile.write(f'{synonyms[-1]}\n')
			else:
				logfile.write('-no synonyms-\n')
			
			if excerpt:
				logfile.write(f'{excerpt}\n{source}\n')
			else:
				logfile.write(f'-no excerpt-\n{source}\n')
			
			if sentences:
				for se in sentences[:-1]:
					logfile.write(f'{se}\n')
				logfile.write(f'{sentences[-1]}\n\n')
			else:
				logfile.write('-no sentences-\n\n')



# MAIN	
main()
