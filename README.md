# um1
UM1 (Understanding Machine One) is a cloud based REST service that provides Natural Language Understanding (NLU) as a Service (UaaS). It can be viewed as providing a "large" language Model in the style of  GPT/3 and Google BERT but it currently cannot generate any language; it is strictly an Understanding Machine. And it isn't large. We have to keep them small because UM1 systems are typically learned using a single Mac Pro Late 2013 (iCan).

If you send it some text, you will instantly get back UM1's Understanding of the text. Its Understanding may differ from yours, just like yours may differ from that of a co-worker, but will still be useful in apps requiring industrial strength NLU

A running UM1 is freely available for alpha testing in the cloud at https://free.understanding-machines.com

This repository contains test programs (starting with just one) and other utilities (in python 3) and test data.

The free alpha version of UM1 is not intended for production use. Syntience Inc does not provide any uptime guarantees. Also, being a demo system, it is not configured to scale very far. If you want to use UM1 for business, contact sales@syntience.com and we will provide a dedicated server as a subscription service. But anyone can use the free UM1 to evaluate UM1 capabilities at this early stage.

To run any of our tests, make sure you can run python3 programs; if not, I recommend the Anaconda release and set that up.

- f.py - run the standard test on the UM1 server. It performs document classification based on semantic similarity between a target sentence and five candidates, one if which is a rephrase of the first (target) phrase.
- chat-200.tsv - Test data file used by f.py

Note that the test file contains phrases that are all questions because we started from test files supplied by quora. They wanted to detect whether two questions are the same in order to fold similar questions together. We use a small randomised subset of question pairs. For more, see https://quoradata.quora.com/First-Quora-Dataset-Release-Question-Pairs . 

So no, this is not a question answering system. It just classifies messages.

If you want to create your own question pairs, you can just create a file with 200 similar-meaning sentence pairs separated by a tab.
A python program to convert such a file to a testset that f.py can use will be posted here.

UM1, and the learning algorithm (Organic Learning) are both discussed at https://experimental-epistemology.ai
