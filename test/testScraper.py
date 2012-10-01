'''
Created on Oct 2, 2012

@author: hasherdene
'''
import unittest
from scraper import fetchChannelList, Channel

class Test(unittest.TestCase):

    def setUp(self):
        pass
    
    def tearDown(self):
        pass

    def testFetch(self):
        channels = fetchChannelList(Channel.FETCH_URL)
        print "\n".join(str(c) for c in channels.items())
        self.assertEqual(len(channels), 16)
    def testStr(self):
        c = Channel(2, "MNB", "current program", "schedule", "icon", "playback")
        self.assertEqual(str(c), "(2) MNB")


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()