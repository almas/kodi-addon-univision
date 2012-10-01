'''
Created on Oct 2, 2012

@author: hasherdene
'''
import unittest

class Test(unittest.TestCase):


    def setUp(self):
        pass

    def tearDown(self):
        pass


    def testUrlParamDecode(self):
        from util import decodeUrlParam
        print decodeUrlParam("channel=2&program=3")


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()