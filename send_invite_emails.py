#!/usr/bin/env python
import json
import os
import smtplib
import sys

#This program takes in a .json file or a directory full of .json files containing the email addresses of students and 
#emails them an invitation to rate their TA.  Must be run from a UCSB server.

def process_file(filename):
    print "---Processing " + filename + " -------"
    try:
        data = json.load(open(filename))
    except (IndexError, IOError):
        print 'Usage: {} emails_json'.format(os.path.basename(sys.argv[0]))
        sys.exit(1)
    except ValueError:
        print '{!r} is not a valid json file'.format(filename)
        sys.exit(1)

    from_email = 'Computer Science Lead TA <leadta@cs.ucsb.edu>'
    subject = 'Computer Science Midterm TA Evaluations'
    template = data['template']

    smtp = smtplib.SMTP()
    smtp.connect('stamps.cs.ucsb.edu')

    for info in data['emails']:
        print 'sending to {!r} \n'.format(info['email'])
        body = template.format(student=info['name'], body=info['output'])
        msg = 'From: {}\nTo: {}\nSubject: {}\n\n{}'.format(
            from_email, info['email'], subject, body)
        smtp.sendmail(from_email, info['email'], msg)
    print
    smtp.quit()


def main():
    if os.path.isdir(sys.argv[1]):   
        for subdir, dirs, files in os.walk(sys.argv[1]):
            for file in files:    
                process_file(subdir+'/'+file)
    else:
        process_file(sys.argv[1])
                
    

    


if __name__ == '__main__':
    sys.exit(main())
