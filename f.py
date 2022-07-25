#! /usr/bin/env python3     # -*-python-*-
# coding: utf-8
# freetest --  Document similarity classification using Jaccard distance
# on moniforms nested in a (possibly deep) JSONArray structure returned from UM1
# Code by Monica Anderson monica@syntience.com 20200811
# Use this code at your own risk any way you want

import sys, os, requests, urllib, json, colorama, time
from colorama import Fore, Style
from datetime import datetime

logtraffic = False                                                              # Set this True to see UM1 network traffic
logjaccard = True                                                              # Demonstrate jaccard score as a distance measure over sets. If this is True, then logoutomes should be set False to avoid ugly output
logoutcomes = False                                                             # Print outcomes of individual tests as single position characters. "=" means ambiguous. "?" means problems. Red is wrong, green is correct guess
logmisc = False                                                                 # Set this True to see other details of tests

logtexts = True                                                                 # These texts are quite verbose so we sometimes tunr these off. They only appear if logjaccard is True
logmoniforms = False                                                            # These moniforms are even more verbose so we turn these off unless we really need them. They only appear if logjaccard is True

testpath = 'chat-200.tsv'                                                       # Test file with 200 string classification tests based on data form Quora Question Pairs (QQP) test benchmark. Feel free to edit those or provide a different file
maxtestlines = 200                                                              # Limit tests to this many lines. None=all test cases in file. Larger files (2000 test cases) are available
writefailurefile = False                                                        # Write failedtests.tsv file of all failing test cases

um1service = "https://free.understanding-machines.com/understand"            # The servicce to use

payload = None                                                                  # Global copy of payload so we can retrieve the texts we sent in when processing the results
testsdone = 0                                                                   # How many test cases that actually returned data to analyze
testfileproblems = 0                                                            # Syntax errors and other problems found in our test data file -- Lines like these should be corrected or replaced
totaltestchars = 0                                                              # Total test characters understood/processed
numberunderstandings = 0                                                        # Total number of strings sent to Understander -- normally 6 per test
truths = []                                                                     # Correct answers -- never sent to UM1
alllines = []                                                                   # Array of input lines -- one test case each

def understand(payload, options):
    try:
        response = requests.post(um1service, json.dumps({'payload':payload, 'options':options}))    # Send payload and Understanding options to UM-1 server
        if response:
            try:
                understanding = response.json()                                 # Parse returned string as JSONObject to return it as a python dict
            except Exception as err:
                print(f"UM-1 understanding exception: {err} -- Response:{response}")  # Exception parsing result JSON. No more information available
                return {"error": err}
            if understanding is not None:                                       # Response parsing succeeded. responsed was received as a JSONObject and was parsed into "understanding" (most often used name) which is a python dict
                if logtraffic:print(f"\npayload='{payload}'\nResult: {json.dumps(understanding)}")
                error = understanding.get('error')                              # Check if there is an error message added by UM1 server or UM1 itself
                if error:
                    print(f"UM-1 error: {error}")                               # If so, print it here so we won't miss it even if caller is not doing proper error checking
                return understanding                                            # In any case, error message or not, return entire JSON to caller
            else:
                print("Response form UM1 is not in valid JSON format")          # Non-exception JSON parse nevertheless did not return a valid result. We expect a python dict of meta-information at this level
        else:
            print("NO response from UM-1")                                      # Non-exception no-response from UM1 -- Typically, we received no JSON to parse.
    except Exception as ex:
        print(f"UM-1 communications exception: {ex}")                           # Serious server side or communications error (such as UM1 restart or network disconnect)
    return None

def createpayload():                                                            # Create a list of testcases which are lists of target and alternatives which are each lists of numbers representing the Understanding of each
    global numberunderstandings, testfileproblems, truths, totaltestchars
    payload = []; testfileproblems = 0; totaltestchars = 0                      # Construct and return a payload based on test file contents. testfileproblems counts syntax errors in test file.
    with open(testpath) as testfile:
        for lineno, line in enumerate(testfile):                                # We read entire file
            if len(line) < 6 or line.startswith('#'): continue                  # We allow comment lines and (nearly) empty lines. They add to line numbers in lineno but not to testcount
            line = line.rstrip()
            alllines.append(line)                                               # Save line, slightly sanitized, in alllines
            parts = line.split("\t")                                            # Separate the tab-separated fields
            if len(parts) < 4:                                                  # We need at least truth, target, and two test cases per test/line (that is why "4") but will happily handle any number of test cases beyond that.
                if lineno < 10: continue                                        # Quietly ignore header lines until we get a bit into the file
                testfileproblems += 1                                           # After those, all lines better have well formatted data in them or we treat it as an error
                continue                                                        # and then we soldier on
            truths.append(int(parts[0]))                                        # Keep truths here. Do not send them to backend because it does not need to know :-) 
            payload.append(parts[1:])                                           # Append the rest of the strings in the testcase (a list of target string and two or more (5 in this case) strings to compare with) to payload list of testcases
            for p in parts[1:]: totaltestchars += len(p)                        # totaltestchars is total numbers of characters in payload
            numberunderstandings += len(parts) - 1                              # Truth is only thing we don't evaluate. We HOPE these are all strings. The count will be off if they are not. This should be counted in backend and returned
            if maxtestlines and maxtestlines <= len(payload): break             # Allow limiting to only a few lines of test cases if so desired.
    return payload

def classifyunderstandings(understandings, of):                                 # understandings is a JSONObject -- it has a few fields of returned metadata, and the result itself is in the field "moniform"
    global testsdone, testfileproblems
    sumofsetsizes = 0; nosemantics = 0; ambiguouscount = 0; correct = 0; incorrect = 0; testsdone = 0; sumofcertainties = 0; certaintiescount = 0; 
    candidatemoniformcount = 0; targetmoniformcount = 0; sumofintersections = 0; sumofunions = 0; emptyintersections = 0; failures = 0

    winoutcome = f"{Fore.GREEN}WIN{Style.RESET_ALL}"
    runnerupoutcome = f"2ND"
    amboutcome = f"{Fore.YELLOW}AMB{Style.RESET_ALL}"
    failoutcome = f"{Fore.RED}FAIL{Style.RESET_ALL}"

    testcases = understandings.get("moniform")                                  # Extract result from returned result + metadata dict/map/JSONObject
    if not testcases or len(testcases) == 0:
        return f" ------ No concepts (moniform) entry in {understandings}"      # UM1 did not return a "moniform" field which is quite surprising
    testindex = 0
    with open("failedtests.tsv", "w") as of2:                                   # Open failed tests output file
        for testindex in range(len(testcases)):                                 # Loop over each of the given test cases (typically 200). A testcases is here a list of (typically six) moniforms (lists of numbers), where first is the target
            testcase = testcases[testindex]
            if logmisc:print(f"length of testcase={len(testcase)}")
            if testcase and len(testcase) >= 3:                                 # Required: a target and at least two candidates to decide between. We typically use five candidates, which means six moniforms per sublist
                targettext = payload[testindex][0]                              # Extract target text for this test case from payload. Note that in payload, there is no truth column so target is index 0
                targetmoniform = testcase[0]                                    # Understanding of target, as the simplest kind of moniform, alist of integers without duplicates, sorted by declining salience estimates
                if logmisc:print(f"length of targetmoniform={len(targetmoniform)}")
                if targetmoniform:
                    candidatemoniforms = testcase[1:]
                    targetmoniformcount += 1                                    # Count actual target moniforms in case we have indefinite number of valid test cases
                    if logmisc:print(f"length of candidatemoniforms={len(candidatemoniforms)}")
                    if candidatemoniforms:
                        candidatemoniformcount += len(candidatemoniforms)
                        targetset = set(targetmoniform)
                        sumofsetsizes += len(targetset)                         # Gather statistics: We track average size for all moniforms whether target or candidate. This is allowed because they will all be coming from the same source
                        winnerindex = -1
                        winnerscore = -1
                        runnerupscore = -1                                      # "margin" statistic tells us the margin between the winner and the runner-up which is a measure of our certainty of the answer
                        ambiguous = 0
                        resulttuples = []
                        certainty = 0
                        
                        for i in range(len(candidatemoniforms)):
                            candmoniform = candidatemoniforms[i]               # loop over all candidate moniforms
                            if candmoniform:
                                if len(candmoniform) == 0: nosemantics += 1
                                candset = set(candmoniform)
                                sumofsetsizes += len(candset)                   # Gather statistics

                                intersection = targetset & candset              # Intersection of target moniform and candidate moniform
                                intersectionlen = len(intersection)
                                
                                union = targetset | candset
                                unionlen = len(union)

                                jaccardscore =  intersectionlen / unionlen      # Compute jaccard distance from target monifor to this candidate moniform

                                if winnerscore == jaccardscore:                 # Tied top score
                                    runnerupscore = jaccardscore
                                    ambiguous += 1                              # Mark this as ambiguous
                                if winnerscore < jaccardscore:                  # New winner
                                    runnerupscore = winnerscore                 # Previous winner becomes the runner-up
                                    winnerscore = jaccardscore
                                    winnerindex = i
                                    ambiguous = 0                               # If we have a clear winner, then we are not ambiguous
                                elif runnerupscore < jaccardscore:              # We must handle the case where the new score beats the runner up score but not the winner score
                                    runnerupscore = jaccardscore

                                sumofintersections += intersectionlen           # Gather statistics
                                sumofunions += unionlen                         # Gather statistics
                                if intersectionlen == 0: emptyintersections += 1
                                truthindex = truths[testindex]
                                resulttuples.append((i, jaccardscore, candmoniform, payload[testindex][0], payload[testindex][i + 1], truthindex)) # extraxt target and candidate texts from payload. offset 0 is target, rest are candidates
                            else: failures += 1

                            ## End of loop over candidates

                        if runnerupscore > -1 and winnerscore > -1:
                            certainty = winnerscore - runnerupscore
                            sumofcertainties += certainty
                            certaintiescount += 1

                        if logjaccard:                                             # demonstrate jaccard score as a distance measure
                            first = True
                            for index, score, moniform, targettext, candtext, truthindex in resulttuples:
                                if first:
                                    print("")
                                    if logmoniforms: print(f"TARGETMONIFORM:                         {targetmoniform}")
                                    if logtexts:     print(f"{Fore.YELLOW + Style.BRIGHT}                                                {targettext}{Style.RESET_ALL}")
                                    first = False
                                candmoniform = candidatemoniforms[index]
                                monidisp = moniform if logmoniforms else ""
                                textdisp = candtext if logtexts else ""
                                scoredisp = round(100.0 * score, 2)
                                certaintydisp = round(100.0 * certainty, 2) if score == winnerscore else ""
                                outcome = ""
                                if index == winnerindex:
                                    if truthindex == index:
                                        if score == runnerupscore:
                                            outcome = amboutcome
                                        else:
                                            outcome = winoutcome
                                    else:
                                        outcome = failoutcome
                                elif score == runnerupscore:
                                    if winnerscore == runnerupscore:
                                        outcome = amboutcome
                                    else:
                                        outcome = runnerupoutcome
                                print(f"  {index}\t{outcome}\t{scoredisp}\t{certaintydisp}\t{monidisp}\t{textdisp}\t")

                # End of test case analysis. 

                testsdone += 1                                                  # Gather statistics
                ambiguouscount += ambiguous                                     # Gather statistics

                if winnerindex == -1:                                           # Ensure we actually have a winner. If not, note that and try next testcase
                    if logoutcomes:
                        sys.stdout.write(f"{Fore.BLUE}?")
                    of.write(f"{Fore.BLUE}?")
                    nosemantics += 1                                            # Count documents where we could not discern any semantics for statistics printout at end
                    continue

                if winnerindex == truthindex:
                    correct += 1                                                # We allow that in case of several equal top scores we guess at the first one of them and if that is correct, then we are correct
                    if ambiguous:
                        if logoutcomes:
                            sys.stdout.write(f"{Fore.GREEN}={Style.RESET_ALL}")     # but we neverteless track that this was an ambiguous win by printing a green equals-sign rather than the guess we guessed
                        of.write(f"{Fore.GREEN}={Style.RESET_ALL}")
                        if writefailurefile: of2.write(f"{winnerindex}\t{alllines[testindex]}\n") # Columns are our guess, truth, target, and all candidates
                    else:
                        if logoutcomes:
                            sys.stdout.write(f"{Fore.GREEN}{winnerindex}{Style.RESET_ALL}") # Green digit is the index of our correct guess
                        of.write(f"{Fore.GREEN}{winnerindex}{Style.RESET_ALL}")
                else:
                    incorrect += 1
                    if writefailurefile: of2.write(f"{winnerindex}\t{alllines[testindex]}\n") # Columns are our guess, truth, target, and all candidates
                    if ambiguous:
                        if logoutcomes:
                            sys.stdout.write(f"{Fore.RED}={Style.RESET_ALL}")       # Ambiguous results where we guessed werong are indicated with a red equals sign
                        of.write(f"{Fore.RED}={Style.RESET_ALL}")
                    else:
                        if logoutcomes:
                            sys.stdout.write(f"{Fore.RED}{winnerindex}{Style.RESET_ALL}") # Red digit is the index of our erroneous guess
                        of.write(f"{Fore.RED}{winnerindex}{Style.RESET_ALL}")
            else: failures += 1

    # Compute some batch-wide statistics and return a summary of what happened for caller to print if they wish

    if logoutcomes: print("");
    accuracy = 0
    avgsetsize = 0
    avgintersectionsize = 0
    margin = 0
    if candidatemoniformcount > 0:
        avgsetsize = round(sumofsetsizes / (targetmoniformcount + candidatemoniformcount), 2)
        avgintersectionsize = round(sumofintersections / (targetmoniformcount + candidatemoniformcount), 2)
        avgunionsize = round(sumofunions / (targetmoniformcount + candidatemoniformcount), 2)
    if testsdone > 0 and sumofsetsizes > 0:
        accuracy = round(100.0 * float(correct) / float(testsdone), 1)
        margin = round(100.0 * float(sumofcertainties) / float(testsdone), 2)
    return f"{Fore.GREEN}Accuracy:{accuracy:>5}% {Fore.YELLOW} avg-margin:{margin:>5}%{Style.RESET_ALL} testsdone:{testsdone:<6} understanding-failures:{failures:<4} meaningless:{nosemantics:<4}avg-setsize:{avgsetsize:<6} avg-intersections:{avgintersectionsize:<6} empty-intersections:{emptyintersections:<4} ambiguous:{ambiguouscount:<4} testfileproblems:{testfileproblems:<4}{Style.RESET_ALL}"

def classifyall(options):
    global um1service, saliencers, testsdone, numberunderstandings, payload
    if logjaccard and logoutcomes:
        print("Cannot use logjaccard and logoutcomes together at this time. Please set one of these two flags to False")
        return
    numberunderstandings = 0 ; starttime = time.time();  serverclass = options.get("server")
    payload = createpayload()                                                   # Make payload globally available so we can translate results back into strings
    if logmisc:
        print(f"Payload={payload}")
        print(f"len(payload)={len(payload)}")
        print(f"len(payload[1])={len(payload[1])}")
    if logtraffic:print(f"serverclass is {serverclass}   um1service URL is {um1service}  options is {options}")
    understandings = understand(payload, options)
    if logtraffic:print(f"understandings={understandings}")
    if understandings:
        numbertests = len(alllines)
        totalticks = understandings.get("totalticks")
        uptimesecs = understandings.get("uptimesecs")
        corpussize = understandings.get("corpussize")
        createdzulu = understandings.get("createdzulu")
        competenceid = understandings.get("competenceid")
        testruntimems = understandings.get("ms")
        competenceuuid = understandings.get("competenceuuid")
        learningtimesecs = understandings.get("learningtimesecs")
        with open("semsimout.txt", "a") as of:
            of.write("\n" + 304 * '=' + "\n")
            of.write(f"Time: {datetime.now().isoformat(timespec='minutes')}  Server Uptime (s): {uptimesecs} Options: {options}\n")
            of.write(f"Corpus of {corpussize} chars learned in {learningtimesecs} seconds - Competence id: {competenceid}  UUID: {competenceuuid}\n")
            of.write("\n\n       ")
            print(f"Time: {datetime.now().isoformat(timespec='minutes')}  Server Uptime (s): {uptimesecs} Options: {options}")
            print(f"Corpus of {corpussize} chars learned in {learningtimesecs} seconds - Competence id: {competenceid}  UUID: {competenceuuid}")

            if logoutcomes:                                                     # Print the fancy two-line header
                print("       ", end="")
                for t in range(1, 1 + int((numbertests + 1) / 10)):
                    print(f"        {t:>2}", end="")
                    of.write(f"        {t:>2}")
                print("\nTest # ", end="")
                of.write("\nTest # ")                                           # Also write it to of
                for u in range(1, numbertests + 1):
                    print(f"{u%10}", end="")
                    of.write(f"{u%10}")
                of.write(f"\n       ")
                print(f"\n       ", end="")
               
            ## Do the actual analysis given the understandings we received above. Margin is jaccard target distance difference from winner to runner-up

            if logjaccard: 
                print(f"\nIndex   Outcome Jaccard Margin")
                print(f"==============================")
            summary = classifyunderstandings(understandings, of)                # Sets testsdone
            if logjaccard:
                print(f"  ^      ^       ^        ^   ")
                print(f"Index   Outcome Jaccard Margin\n")
            print(summary)
            of.write(summary)
            of.write("\n")
            elapsed = time.time() - starttime
            servicetime = 0
            cps = 0
            if testsdone > 0:
                if testruntimems: 
                    servicetime = int(testruntimems)
                    cps = round(1000 * totaltestchars / testruntimems)
                avgstring = f" Average is {(1000.0 * elapsed / testsdone):<.4} ms/test"
                avbbackendtime = f" Average is {(servicetime / testsdone):<.4} ms/test   {(servicetime / numberunderstandings):<.4} ms/sample   Speed was {cps} cps "
            else:
                avgstring = ""
                avbbackendtime = ""
            print(f"For {testsdone} tests with a total of {numberunderstandings} samples, total {totaltestchars} chars, real time was {int(elapsed * 1000):>5} ms {avgstring}  Batch service time: {servicetime} ms{avbbackendtime}")  
            testsdone = 0
            
if __name__ == '__main__':          
    classifyall({"topn" : 60, "debug" : False})
