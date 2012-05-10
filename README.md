# course_lists.py

## Overview

This tool was made to easily obtain and combine course lists for the Computer
Science department. The `output.json` file produced by `course_list.py`
contains the email and name for students, teaching assistants and the instructor
of each class.

## Requirements

In order to obtain the course lists from UCSB eGRADES, you must have a UCSB
NetID and have `proxy` access to the courses on eGRADES. Furthermore to
associate the TAs with the course, you will need a CSV created from the `TA
assignments` file that the Graduate Affairs Manager typically creates. Finally,
the email association depends on the correct mapping of names to some of the
directories hosted on the Computer Science server.

## Running

This tool depends on the
[BeautifulSoup](http://www.crummy.com/software/BeautifulSoup/) and
[requests](http://docs.python-requests.org/) packages. These can be installed
via `pip install beautifulsoup` and `pip install requests` respectively.

Once these are installed, you may simply download and run the program like so:

    ./course_lists.py --save tmp TA_Assignments.csv

You will be prompted for your UCSB NetID credentials, and prompted again for
any students, TAs or instructors for which an email mapping cannot be
found. Upon completion, the program will produce the file `output.json` in the
same directory as course_lists.py.

The `--save tmp` option is not required, however, it saves a CSV for all the
course rosters in the folder `tmp`. These can be used for external processing,
and be used to more quickly regenerate `output.json` should something have gone
wrong. To make use of the saved CSV files run via:

    ./course_lists.py --load tmp TA_Assignments.csv
