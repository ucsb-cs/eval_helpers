#!/usr/bin/env python
import csv
import getpass
import json
import os
import re
import requests
import sys
from BeautifulSoup import BeautifulSoup
from optparse import OptionParser
from urlparse import urljoin


EMAILS = {'Singh A K': 'ambuj@cs.ucsb.edu',
          'Hardekopf B C': 'benh@cs.ucsb.edu',
          'Costanzo C': 'mikec@cs.ucsb.edu',
          'Koc C K': 'koc@cs.ucsb.edu',
          'Moser L E': 'moser@ece.ucsb.edu',
          'Buoni M J': 'buoni@cs.ucsb.edu',
          'Manjunath B S': 'manj@ece.ucsb.edu',
          'Sen P': 'psen@ece.ucsb.edu',
          'Tessaro S M': 'tessaro@cs.ucsb.edu',
          'Kim T': 'kim@mat.ucsb.edu'}
CSV_COURSE_COL = 0
CSV_INSTRUCTOR_COL = 1
CSV_TA_COL = 2

#parent class with debugging features, and html requests
class StupidUCSBWebApp(object):
    PREFIX = 'ctl00$pageContent${}'

    def __init__(self, debug=False):
        self.session = requests.session()
        self.view_state = None
        self.event_validation = None
        self.debug = debug

    def request(self, url, data=None, soupify=True, disable_debug=False):
        if self.debug:
            print('Fetching {0}'.format(url))
            if data and not disable_debug:
                print('{!s}\n'.format(data))
            elif data:
                print('POST data hidden\n')
        if not data:
            # verify=False ignores ssl certs... sometimes it seems the coursesearch cert is broken
            r = self.session.get(url, verify=False)
        else:
            params = {'__VIEWSTATE': self.view_state,
                      '__EVENTVALIDATION': self.event_validation}
            for param, value in data.items():
                if param.endswith('.?'):
                    params[self.PREFIX.format(param.replace('?', 'x'))] = value
                    params[self.PREFIX.format(param.replace('?', 'y'))] = value
                else:
                    params[self.PREFIX.format(param)] = value
            r = self.session.post(url, data=params)
        if r.status_code != 200:
            raise Exception('Status code: {}'.format(r.status_code))
        if soupify:
            soup = BeautifulSoup(r.text)
            self.update(soup)
            return soup, r
        return r

    def update(self, soup):
        value = lambda x:str(soup('input', id=x)[0]['value'])
        self.view_state = value('__VIEWSTATE')
        self.event_validation = value('__EVENTVALIDATION')

    def verify_url(self, expected, url):
        if expected != url:
            raise Exception('Expected {!r} Found {!r}'.format(expected, url))

#this class downloads all of the students from the UCSB egrades website, the person running this
#script must be marked as a proxy on egrades.
class Egrades(StupidUCSBWebApp):
    URL_BASE = 'https://egrades.sa.ucsb.edu/'
    URL_DOWNLOAD = urljoin(URL_BASE, 'ClasslistDownload.aspx')
    URL_GRADEBOOK = urljoin(URL_BASE, 'Gradebook.aspx')
    URL_INSTRUCTOR = urljoin(URL_BASE, 'InstructorMain.aspx')

    def login(self):
        print "Connecting to egrades"
        url = urljoin(self.URL_BASE, 'Login.aspx')
        self.request(url)
        while True:
            sys.stdout.write('Username: ')
            username = sys.stdin.readline().strip()
            password = getpass.getpass()
            _, r = self.request(url, {'txtUCSBNetID': username,
                                      'txtPassword': password,
                                      'btnContinue.?': 0},
                                disable_debug=True)
            if r.url != url:
                return
            print('Login failed, try again.')

    def find_courses(self, quarter, faculty_email):
        # Make proxy selection
        print "Downloading class lists..."
        url = urljoin(self.URL_BASE, 'RoleSelection.aspx')
        soup, r = self.request(url, {'roleSelectList': 'Proxy',
                                     'continueButton.?': 0})
        self.verify_url(self.URL_INSTRUCTOR, r.url)
        current_quarter = soup('option', selected='selected')[0]['value']
        # Update quarter if necessary
        if quarter and current_quarter != quarter:
            soup, r = self.request(self.URL_INSTRUCTOR,
                                   {'ddlQuarterList': quarter})
            self.verify_url(self.URL_INSTRUCTOR, r.url)
            self.quarter = quarter
        else:
            self.quarter = current_quarter
        for item in soup('input', type='image'):
            #print "ITEM:"
            #print item
            value = item['name'][len(self.PREFIX) - 2:]
            if 'Secondary' in value:
                continue

            # Skip classes with no students
            students_raw = item.parent.parent.findAll('td')[4].contents[0]
            num_students = int(students_raw.strip().split('/')[0])
            if num_students <= 0:
                continue
                
            prof_raw = item.parent.parent.findAll('td')[2].contents[0]
            professor = prof_raw.rstrip('&nbsp;').strip().title()
            email = faculty_email.get_email(professor)

            yield ''.join(item['title'].split()[1:3]), {'name': professor, 'email': email}, value

    def fetch_course_list(self, course_key, save_dir):
        # Visit class page
        _, r = self.request(self.URL_INSTRUCTOR, {'{}.?'.format(course_key): 0})
        self.verify_url(self.URL_GRADEBOOK, r.url)

        _, r = self.request(self.URL_GRADEBOOK, {'btnDownloadGradesTop.?': 0})
        self.verify_url(self.URL_DOWNLOAD, r.url)
        r = self.request(self.URL_DOWNLOAD, {'Download.?': 0}, soupify=False)
        if 'content-disposition' not in r.headers:
            raise Exception('Did not receive the expected file')
        if save_dir:
            filename = r.headers['content-disposition'].split('=')[1]
            if not os.path.isdir(save_dir):
                os.makedirs(save_dir)
            with open(os.path.join(save_dir, filename), 'w') as fp:
                fp.write(r.text)
            print('Saved: {}'.format(filename))
        self.request(self.URL_INSTRUCTOR)
        return get_students(r.text)


class CSFacultyEmail(object):
    URL = 'http://cs.ucsb.edu/courses/schedules/'
    CS_RE = re.compile('cs.ucsb.edu/%7E(.+)$')

    def __init__(self):
        r = requests.get(self.URL)
        self.soup = BeautifulSoup(r.text)

    def get_email(self, name):
        if name in EMAILS:
            return EMAILS[name]
        result = self.soup.find('td', text=name)
        if result and result.parent.name == 'a':
            url = result.parent['href']
            match = self.CS_RE.search(url)
            if match:
                return '{}@cs.ucsb.edu'.format(match.group(1))
        return ask_for_email(name)

class CSGradEmail(object):
    @staticmethod
    def first_last(name):
        parts = name.split()
        return '{} {}'.format(parts[0], parts[-1])

    def __init__(self):
        r = requests.get('http://cs.ucsb.edu/~bboe/p/list_grads')
        soup = BeautifulSoup(r.text)
        self.mapping = {}
        for row in soup.findAll('tr'):
            if row.th:
                continue
            name_anchor = row('td')[0]('a')[0]
            name = self.first_last(name_anchor.contents[0])
            assert(name not in self.mapping) # potential for duplicates
            self.mapping[name] = name_anchor['href'][7:]

    def get_email(self, name):
        name_key = self.first_last(name)
        if name_key in self.mapping:
            return self.mapping[name_key]
        return ask_for_email(name)

#not sure why we get instructor names from the course catalog when they exist the exact same on egrades
#so i commented this out
#class CourseCatelog(StupidUCSBWebApp):
#    URL = 'https://my.sa.ucsb.edu/public/curriculum/coursesearch.aspx'
#
#    def get_instructors(self, quarter, include, faculty_email):
#        self.request(self.URL)
#        soup, _ = self.request(self.URL, {'courseList': 'CMPSC',
#                                          'quarterList': quarter,
#                                          'dropDownCourseLevels': 'All',
#                                          'searchButton.?': 0})
#        course_rows = soup('tr', attrs={'class': 'CourseInfoRow'})
#        seen = set()
#        for course_row in course_rows:
#            name_td = course_row('td')[1]
#            name_td.div.extract()
#            course = name_td.contents[0].strip().replace(' ', '').lower()
#            if course not in seen and course in include:
#                course_row('td')[4].div.extract()
#                instructor = course_row('td')[5].contents[0].strip().title()
#                email = faculty_email.get_email(instructor)
#                yield course, {'name': instructor, 'email': email}
#                seen.add(course)


def get_tas(ta_csv_file, include, grad_email):
    try:
        tas_csv = csv.reader(open(ta_csv_file), delimiter=',', quotechar='"')
    except IOError:
        sys.stderr.write('{!r} does not exist\n'.format(ta_csv_file))
        sys.exit(1)
    name_re = re.compile('^[A-Za-z -]+$')

    for row in tas_csv:
        course_field = row[CSV_COURSE_COL].strip()

        if not course_field or not course_field[CSV_COURSE_COL].isdigit():
            continue
        instructor = row[CSV_INSTRUCTOR_COL].strip().title()
        course = 'cmpsc{}'.format(course_field).lower()
        if format_course_key(course,instructor) not in include:
            print('Ignoring course {!r}'.format(course))
            continue
        tas = []
        for item in row[CSV_TA_COL:]:
            if not item:
                 continue
            if 'reader' in item.lower() or not name_re.match(item):
                print('Skipping {!r} for {!r}'.format(item, course))
                continue
            name = item.strip()
            email = grad_email.get_email(name)
            tas.append({'name': name, 'email': email})
        yield course, instructor, tas


def ask_for_email(name):
    sys.stdout.write('Email needed for {!r}: '.format(name))
    sys.stdout.flush()
    return sys.stdin.readline().strip()


def get_students(data):
    students = []
    for row in csv.reader(data.split('\n')[1:]):
        if not row:
            continue
        name = '{} {}'.format(row[5], row[4]).strip().title()
        email = row[10].strip()
        grade = row[2].strip()
        #ignore students who have withdrawn
        if grade is 'W':
            continue
        if not email:
            email = ask_for_email(name)
        students.append({'name': name, 'email': email})
    return students

def format_course_key(course, instructor):
    name=''
    #If the person has two last names, we want both of them, otherwise just their last name, no initials
    if len(instructor.split(" ")) > 1 and len(instructor.split(" ")[1]) > 1:
        name =  instructor.split(" ")[0] + "_" + instructor.split(" ")[1]
    else:
        name = instructor.split(" ")[0]
    
    return course.lower()+'_'+name.lower()

def main():
    msg = {'load': 'When provided, course rosters are loaded from DIR.',
           'save': 'When provided, course rosters are saved to DIR.',
           'quarter': ('When provided, fetch the course list for the specified '
                       'quarter in the format YYYYQ, where Q should be 1 for '
                       'Winter, 2 for Spring, 3 for Summer and 4 for Fall. When'
                       ' not provided, the current quarter is obtained via '
                       'egrades or the loaded course rosters.')}
    parser = OptionParser('Usage: %prog [options] TA_CSV_FILE')
    parser.add_option('-l', '--load', metavar='DIR', help=msg['load'])
    parser.add_option('-s', '--save', metavar='DIR', help=msg['save'])
    parser.add_option('-q', '--quarter', help=msg['quarter'])
    parser.add_option('-d', '--debug', action='store_true')
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error('Must provide TA_CSV_FILE argument')
    elif not args[0].lower().endswith('.csv') :
        parser.error('The file provided must be a .CSV file')
        

    # error on mutually exclusive options
    for x, y in (('load', 'save'), ('load', 'quarter')):
        if getattr(options, x) and getattr(options, y):
            parser.error('--{} and --{} cannot both be provided.'.format(x, y))
    # Initialize requests
    faculty_email = CSFacultyEmail()
    grad_email = CSGradEmail()

    # fetch or load student to course mapping
    course_data = {}
    if options.load:
        for filename in os.listdir(options.load):
            path = os.path.join(options.load, filename)
            students = get_students(open(path).read())
            course_data[filename.split('_')[1].lower()] = {'students': students}
        quarter = filename.split('_', 1)[0]
        quarter = '20{}{}'.format(quarter[1:],
                                  {'W': 1, 'S': 2, 'M': 3, 'F': 4}[quarter[0]])
    else:
        e = Egrades(debug=options.debug)
        e.login()
        for course, instructor, value in e.find_courses(options.quarter, faculty_email):
            students = e.fetch_course_list(value, options.save)
            print 'course:' + course + ' professor:' + str(instructor)
            course_data[ format_course_key(course,instructor['name']) ] = {'students': students}
            course_data[ format_course_key(course,instructor['name']) ]['instructor'] = instructor
        quarter = e.quarter
    course_set = set(course_data)

    #not sure why we get instructor names from the course catalog when they exist the exact same on egrades
    #so i commented this out
    # add instructor information to courses
    #c = CourseCatelog(debug=options.debug)
    #courses = c.get_instructors(quarter, course_set, faculty_email)
    #for course, instructor in courses:
    #    print course
    #    print instructor
    #    course_data[course+"|"+instructor['name']]['instructor'] = instructor

    # add ta information to courses
    for course, instructor, tas in get_tas(args[0], course_set, grad_email):
        course_data[ format_course_key(course,instructor) ]['tas'] = tas

    json.dump(course_data, open('output.json', 'w'))


if __name__ == '__main__':
    sys.exit(main())
