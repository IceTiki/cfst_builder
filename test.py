# -*- coding: mbcs -*-
# print(dir())
print(__main__)
print(__package__)
print(__name__)
print(__builtins__)

from abaqus import *
from abaqusConstants import *
from caeModules import *
from driverUtils import executeOnCaeStartup
import urllib2



def http_get(url):
    response = urllib2.urlopen(url)
    content = response.read()
    return content


# ret = http_get("https://www.baidu.com")
# print(ret)
