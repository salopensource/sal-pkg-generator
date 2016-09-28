#!/usr/bin/python
import subprocess
import os
import sys
import argparse
from time import localtime
import tempfile
import json

from Foundation import *

BUNDLE_ID = 'com.github.salopensource.sal'

def pref(pref_name):
    pref_value = CFPreferencesCopyAppValue(pref_name, BUNDLE_ID)
    if pref_value == None:
        pref_value = default_prefs.get(pref_name)
        # we're using a default value. We'll write it out to
        # /Library/Preferences/<BUNDLE_ID>.plist for admin
        # discoverability
        set_pref(pref_name, pref_value)
    if isinstance(pref_value, NSDate):
        # convert NSDate/CFDates to strings
        pref_value = str(pref_value)
    return pref_value

def curl(url, data=None):
    if data:
        cmd = ['/usr/bin/curl','--max-time','30','--connect-timeout', '10', '--data', data, url]
    else:
        cmd = ['/usr/bin/curl','--max-time','30', '--connect-timeout', '10', url]
    task = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = task.communicate()
    if task.returncode == 0:
        stderr = None
    return stdout, stderr

def download_scripts(server_scripts, install_dir, server_url):
    """ Downloads remote scripts to pkg root.
    """
    for server_script in server_scripts:
        download_and_write_script(server_script, install_dir, server_url)

def download_and_write_script(server_script, install_dir, SERVER_URL):
    """
    Downloads a named script from the server, writes it and makes it execuatble.
    """
    script_url = "%s/preflight-v2/get-script/%s/%s/" % (SERVER_URL, server_script['plugin'], server_script['filename'])
    stdout, stderr = curl(script_url)
    if stderr:
        print 'Error received downloading script %s:' % script_url
        print stderr
        sys.exit(1)

    script = open (os.path.join(install_dir, server_script['plugin'], server_script['filename']), 'w')
    try:
        data = json.loads(stdout)
    except:
        print 'Did not receive valid JSON when requesting script content.'
        sys.exit(1)

    script.write(data[0]['content'])
    script.close()
    os.chmod(os.path.join(install_dir, server_script['plugin'], server_script['filename']), 0755)

def create_dirs(server_scripts, install_dir):
    """ Creates any directories needed for external scripts
    (named after the plugin)
    """

    for item in server_scripts:
        if not os.path.exists(os.path.join(
            install_dir,
            item['plugin']
            )
            ):
            os.makedirs(os.path.join(install_dir,item['plugin']))

def get_checksum(SERVER_URL):
    """ Downloads the checkum of existing scripts.
    Returns:
        A dict with the script name, plugin name and hash of the script
        or None if no external scripts are used.
    """


    preflight_url = "%s/preflight-v2/" % SERVER_URL
    stdout, stderr = curl(preflight_url)

    if stderr:
        print stderr
        sys.exit(1)
    stdout_list = stdout.split("\n")
    if "<h1>Page not found</h1>" not in stdout_list:
        print stdout

    try:
        return json.loads(stdout)
    except:
        print 'Didn\'t receive valid JSON from Server.'
        sys.exit(1)

def main():
    if os.getuid() != 0:
        print 'You need to run this as root.'
        sys.exit(1)

    parser = argparse.ArgumentParser(
    description='Builds a package containing Sal\'s external scripts')
    parser.add_argument(
    '--serverurl', help='Disable updates to built image via AutoDMG',
    default=pref('ServerURL'))
    parser.add_argument("-o", "--output-dir", default=os.getcwd(),
        help=("Output directory for built package and uninstall script. "
              "Directory must already exist. Defaults to the current "
              "working directory."))

    args = parser.parse_args()

    # Make pkg root
    pkg_root = tempfile.mkdtemp()
    install_dir = os.path.join(pkg_root, 'usr', 'local', 'sal', 'external_scripts')
    os.makedirs(install_dir)
    # Get scripts for download
    server_scripts = get_checksum(args.serverurl)
    if server_scripts:
        # Download all scripts
        create_dirs(server_scripts, install_dir)
        download_scripts(server_scripts, install_dir, args.serverurl)

    print install_dir

    # Build pkg

    preinstall_script = """#!/bin/bash
/bin/rm -rf /usr/local/sal/external_scripts"""

    script_dir = os.path.join(tempfile.mkdtemp(), 'Scripts')
    os.makedirs(script_dir)
    script_path = os.path.join(script_dir,'preinstall')
    with open(script_path, "w") as fd:
        fd.write(preinstall_script)
    os.chmod(script_path, 0755)


    now = localtime()
    version = "%04d.%02d.%02d" % (now.tm_year, now.tm_mon, now.tm_mday)
    pkg_name = 'sal_external_scripts-%s.pkg' % version
    output_path = os.path.join(args.output_dir, pkg_name)
    pkgbuild = '/usr/bin/pkgbuild'
    cmd = [pkgbuild,
           "--root", pkg_root,
           "--identifier", 'com.github.salopensource.sal.external_scripts',
           "--version", version,
           "--scripts", script_dir,
           output_path]


    subprocess.call(cmd)

if __name__ == '__main__':
    main()
