#! /usr/bin/python3

import re
import os
import json

from urllib import request as http
from bs4 import BeautifulSoup as Parse

# Prompt user input from command line
def getUserInput (valid, prompt, hint = "", failed = "Error: Invalid input"):
	"""
	Prompts user for and validates input using regular expression
	@params:
		valid 		- Required 	: regex to validate against (Rgx)
		prompt 		- Required 	: verbose user prompt (Str)
		hint 		- Optional 	: input hint (Str)
		failed 		- Optional 	: failed input (Str)
	Returns: dicts (List)
	"""
	response = input(prompt).strip()
	if re.match(valid, response):
		return response
	print(failed)
	return getUserInput(valid, prompt, hint, failed)

# Print iterations progress
def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 50, fill = '█'):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print('\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix), end = '\r')
    # Print New Line on Complete
    if iteration == total: 
        print()

# Get Count of Results From Search - The Regex Assumes No More Than 99,999 Results
def getResultCount (html):
	header = html.find('h1').string.strip()
	results = re.findall(r"[0-9]{1,5}\sResults", header)
	if len(results) == 1:
		nResults = int(results[0].replace("Results", "").strip())
	else:
		nResults = 0
	return nResults

# Get Article Links on Search Page
def getArticleLinks (html):
	articles = []
	links = html.find_all("a", {"class": "highwire-cite-linked-title"})
	for link in links:
		if link.string is not None:
			href, title = link.get("href"), link.string.strip()
		else:
			href, title = link.get("href"), link.get("href") # Set Title to Link if No Title is Available
		articles.append((href, title))
	return articles

# Get Download Link From Article Page
def getDownloadLink (html):
	href = html.select_one("div.pane-content p a[target='_blank']").get("href")
	return href

if __name__ == "__main__":

	maxArticles = 10000

	# Get Search Term
	searchTerm = getUserInput(r"[a-zA-Z0-9\-\:\s]{1,128}", "Enter bioRxiv Search Term: ", hint = "Search can should match regex: [a-zA-Z0-9\-\:]{1, 128}")

	# Define Directories
	homeDir = os.path.dirname(os.path.realpath(__file__))
	downloadDir = homeDir + "/downloads/" + searchTerm
	cacheDir = homeDir + "/cache"

	# Create Directories if Required
	if not os.path.isdir(downloadDir):
		os.makedirs(downloadDir)
	if not os.path.isdir(cacheDir):
		os.makedirs(cacheDir)

	# Set Domain & Query
	domain = "https://www.biorxiv.org"
	options = {
		"numresults" 	: str(maxArticles),
		"sort" 			: "relevance-rank"
	}

	# Set Cache
	cacheFile = cacheDir + "/" + searchTerm + ".json"
	if searchTerm.replace(" ", "-") + ".json" not in os.listdir(cacheDir):
		with open(cacheFile, "w") as handle:
			json.dump([], handle)

	# Generate Query & Concatenate URL
	query = "/search/" + searchTerm + "".join(["%20" + k + "%3A" + v for k, v in options.items()])
	url = domain + query
	
	# Search (Root) Request
	req = http.Request(url)
	with http.urlopen(req) as res:
		html = Parse(res.read(), "html.parser")
		n = getResultCount(html)
		print("Found %d Results for Search Term: %s" % (n, searchTerm))
		articles = getArticleLinks(html)
		assert len(articles) == n, "Error: Number of articles does not match available links."

	# Retrieve Cache if Available
	cachedLinks = []
	if searchTerm.replace(" ", "-") + ".json" in os.listdir(cacheDir):
		with open(cacheFile, "r") as handle:
			cache = json.load(handle)
			cachedLinks = [record["search-href"] for record in cache]

	# Build Queue
	articleQueue = []
	for href, title in articles:
		if href not in cachedLinks:
			articleQueue.append((href, title))

	# Get Article Download Links
	i, l = 0, len(articleQueue)
	if l > 0:
		print("%d of %d Links Scraped" % (len(cachedLinks), n))
		printProgressBar(i, l, prefix = "Retrieving Download Links:", suffix = "(%d/%d)" % (i, l))
		while l > 0:
			href, title = articleQueue.pop(0)
			try:
				req = http.Request(domain + href)
				with http.urlopen(req) as res:
					html = Parse(res.read(), "html.parser")
					downloadLink = getDownloadLink(html)
					record = {
						"search-href" : href,
						"title" : title,
						"download-href" : downloadLink
					}
					# Append Record to Cache (Update) - Not Ideal But it Works
					with open(cacheFile, "r") as handle:
						cache = json.load(handle)
						cache.append(record)
					with open(cacheFile, "w") as handle:
						json.dump(cache, handle)
				i += 1
				printProgressBar(i, l, prefix = "Retrieving Download Links:", suffix = "(%d/%d)" % (i, l))
			except KeyboardInterrupt:
				raise
			except:
				# Re-Append to Article Queue if Request Fails
				articleQueue.append((href, title))
	
	# Load Cache
	cache = []
	if len(cache) == 0:
		with open(cacheFile, "r") as handle:
			cache = json.load(handle)

	# Add Undownloaded But Cached Articles to Download Queue
	downloadQueue = []
	downloaded = os.listdir(downloadDir)
	for record in cache:
		if record["title"] + ".pdf" not in downloaded:
			downloadQueue.append(record)
	
	# Download Articles
	i, l = 0, len(downloadQueue)
	if l > 0:
		print("%d of %d Have Been Downloaded" % (l, n))
		printProgressBar(i, l, prefix = "Downloading PDFs:", suffix = "(%d/%d)" % (i, l))
		while l > 0:
			record = downloadQueue.pop(0)
			try:
				req = http.Request(record["download-href"])
				with http.urlopen(req) as res:
					with open(downloadDir + "/" + record["title"] + ".pdf", "wb") as pdf:
						pdf.write(res.read())
				i += 1
				printProgressBar(i, l, prefix = "Downloading PDFs:", suffix = "(%d/%d)" % (i, l))
			except KeyboardInterrupt:
				raise
			except:
				# Re-Append to Download Queue if Request Fails
				downloadQueue.append(record)
	else:
		print("No Articles Available for Download.")

else:
	pass