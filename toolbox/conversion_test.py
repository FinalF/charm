'''
Created on Jul 5, 2011

@author: urbanus
'''
from toolbox.conversion import Conversion
import unittest


class Test(unittest.TestCase):


    def testOS2IP(self):
        #9,202,000 = (0x)8c 69 50. 
        i = Conversion.OS2IP(b'\x8c\x69\x50')
        self.assertEqual(i, 9202000)
        
    def testIP2OS(self):
        #9,202,000 = (0x)8c 69 50. 
        os = Conversion.IP2OS(9202000)
        self.assertEqual(os, b'\x8c\x69\x50')

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testOS2IP']
    unittest.main()