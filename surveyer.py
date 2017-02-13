#!/usr/bin/env python


import os, sys, re
import uuid
import json 

import logging
from logging.handlers import WatchedFileHandler
import ConfigParser

import bibtexparser
import bibtexparser.customization 
import pybtex

'''
TODO:
* a reference manager to implement prototype design pattern
* cross-platform support 
* a configuration file
* GUI support
* online refreshment of bibtex library
'''
class Reference(object):
    def __init__(self, citation_key =""):
        super(Reference, self).__init__()
        global g_bib_database
        self.raw_record = g_bib_database.entries_dict[citation_key] 
        record = self.raw_record.copy()
        record = bibtexparser.customization.type(record)
        record = bibtexparser.customization.author(record)
        record = bibtexparser.customization.editor(record)
        record = bibtexparser.customization.journal(record)
        record = bibtexparser.customization.keyword(record)
        record = bibtexparser.customization.link(record)
        record = bibtexparser.customization.page_double_hyphen(record)
        record = bibtexparser.customization.doi(record)
        self.citation_key = citation_key
        record.setdefault("title", "")
        record.setdefault("author", [])
        record.setdefault("journal", "")
        record.setdefault("year", "")
        self.author = record["author"]
        self.title = record["title"]
        self.journal = record["journal"]
        self.year = record["year"]

        
    def format(self):
        citation = "%s. %s. %s [Fields missing]\n" % (",".join(self.author), self.title, self.year)
        try:
            tmp_db = bibtexparser.bibdatabase.BibDatabase()
            tmp_db.entries = [self.raw_record]
            pe = pybtex.PybtexEngine()
            writer = bibtexparser.bwriter.BibTexWriter()
            bibtex_text = writer.write(tmp_db)
            citation = pe.format_from_string(bibtex_text, "unsrt", output_backend="plaintext")
            citation = citation.replace("[1]", "")
        except:
            pass
        return citation.encode("utf-8", "replace")
    
    def __str__(self):
        return self.format()
 
class Bibliography(object): # a construct to publish a bibliography list with specified format
    def __init__(self, citation_keys = [], format = "unsrt"):
        super(Bibliography, self).__init__()
        self.citation_keys = citation_keys
        self.format = format
        
    def set_format(self, format = "unsrt"):
        self.format = format
        
    def append(self, key):
        self.citation_keys.append(key)
        
    def add_keys(self, keys):
        self.citation_keys += keys
        
    def add(self, other_bib):
        self.citation_keys += other_bib.citation_keys 

    def publish_key(self, key):
        if key not in self.citation_keys: return key
        if self.format == "unsrt":
            citation_order = self.citation_keys.index(key) + 1
            return "[%d]" % (citation_order) 
        return "[%s]" % key
    
    def publish(self):
        bibliography_text = "\n"
        for citation_key in self.citation_keys:
            r = Reference(citation_key)
            pub_key = self.publish_key(citation_key)
            bibliography_text += "%s %s" % (pub_key, r) 
        return bibliography_text


class Text(object): 
    def __init__(self, title = "", content = ""):
        super(Text, self).__init__()
        self.content = content
        self.title = title
        citation_keys = []
        for citation_key in re.findall('\[@(\w+)\]', self.content):
            if g_bib_database.entries_dict.has_key(citation_key) and citation_key not in citation_keys:
                citation_keys.append(citation_key)
        self.bibliography = Bibliography(citation_keys)

    def __str__(self):
        return "### %s  \n%s" % (self.title, self.content)
    
    def format_citations(self, format="unsrt"):
        formatted_content = "# %s \n" % self.title + self.content[:]
        if len(self.bibliography.citation_keys) == 0: return formatted_content
        self.bibliography.set_format(format)
        for citation_key in self.bibliography.citation_keys:
            formatted_content = formatted_content.replace("[@%s]" % (citation_key), 
                                                          self.bibliography.publish_key(citation_key)) 
        return formatted_content + "\nBibliography\n" + self.bibliography.publish()

g_idea_title_pattern = '^### ([^\r\n]+)$'
g_idea_title_pattern2 = '^### [^\r\n]+$'

class Idea(Text): # a subclass of Text that can leave the title auto-generated
    def __init__(self, title = "", content = ""):
        super(Idea, self).__init__(title, content)
        global g_idea_title_pattern
        m = re.search(g_idea_title_pattern, content)
        if m is not None:
            self.title = m.group(1)
            self.content = re.sub(g_idea_title_pattern, "", content) #remove title line
        elif title == "":
            self.title = "Idea-" + str(uuid.uuid4()) # generate the title automatically
    

class Topic(Text): # a Topic contains one or more Ideas
    def __init__(self, title = "default", content = "", fname="topic-*.md"):
        super(Topic, self).__init__(title, content)
        self.fname = fname
        self.ideas = []
        idea_names = re.findall(g_idea_title_pattern, content, re.MULTILINE)
        if len(idea_names) > 0:
            idea_contents = re.split(g_idea_title_pattern2, content, flags=re.MULTILINE)[1:]
        for i in xrange(len(idea_names)):
            self.ideas.append(Idea(idea_names[i], idea_contents[i]))
    def __str__(self):
        return "# %s  \n\n%s" % (self.title, self.content)


global g_bib_database, g_topic_list
g_bib_database = None
g_topic_list = []

bibfile_path = "E:\\mendeley\\library.bib"
topics_path = "E:\\Syncs\\Core\\Research"
pdffile_path = "E:\\mendeley"


log_unit = "surveyer"
probe_logger = logging.getLogger('')
probe_logger.setLevel(logging.ERROR)
formatter = logging.Formatter(log_unit + '(%(lineno)s) [%(levelname)s]%(asctime)s: %(message)s')
file_handler = WatchedFileHandler(log_unit + ".log")
file_handler.setFormatter(formatter)
probe_logger.addHandler(file_handler)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
probe_logger.addHandler(stream_handler)


def representsInt(s):
    try: 
        int(s)
        return True
    except ValueError:
        return False

import cmd
import string, sys

class CLI(cmd.Cmd):
    def __init__(self):
        cmd.Cmd.__init__(self)
        
    def precmd(self, line):
        self.load_config()
        return line
        
    def load_config(self):
        global g_bib_database, g_topic_list
        global bibfile_path, topics_path
        if not os.path.isfile(bibfile_path):
            logging.error("Cannot open your specified bibtex file %s" % (bibfile_path))
            sys.exit(1)

        with open(bibfile_path) as bibtex_file:
            bibtex_text = bibtex_file.read().decode("utf-8", "replace")
            g_bib_database = bibtexparser.loads(bibtex_text)
            
        if not os.path.isdir(topics_path):
            logging.error("No topics found on path %s" % (topics_path))
            sys.exit(1)

        topic_fnames = [fname 
                       for fname in os.listdir(topics_path) 
                        if os.path.isfile(os.path.join(topics_path, fname))]
       
        g_topic_list = [] 
        for fname in topic_fnames:
            m = re.match("^topic-(.*)\.md$", fname)
            if m is not None:
                topic_title = m.group(1).replace("-", " ").title()
                abs_path = os.path.join(topics_path, fname)
                with open(abs_path) as fstream:
                    topic_content = fstream.read()
                    m = re.search("^#\s+(.*)\s*\n", topic_content)
                    if m is not None:
                        topic_title = m.group(1)
                g_topic_list.append(Topic(topic_title, topic_content, fname))

        self.current_topic = 0
        self.all_bib = Bibliography(g_bib_database.entries_dict.keys())
        self.all_referenced_bib = Bibliography([])
        self.all_ideas = []
        for topic in g_topic_list:
            self.all_referenced_bib.add(topic.bibliography)
            self.all_ideas += topic.ideas
        self.balance_state()

    
    def balance_state(self):
        if self.current_topic < 0 or self.current_topic > len(g_topic_list):
            logging.critical("TOPIC-NUM %d out of range [0-%d]." %(self.current_topic, len(g_topic_list)))
            sys.exit(0)
        if self.current_topic == 0:
            self.prompt = '> '
            self.active_topics = g_topic_list
            self.active_bib = self.all_referenced_bib 
            self.active_ideas = self.all_ideas
        else:
            topic = g_topic_list[self.current_topic-1]
            self.prompt = topic.title + "> "
            self.active_topics = [topic]
            self.active_bib = topic.bibliography
            self.active_ideas = topic.ideas

    def do_show(self, arg):
        args = arg.split(" ")
        if len(args) == 0: 
            self.help_open()
            return
        key = args[0]
        if key in self.all_bib.citation_keys:
            r = Reference(key)
            print r.format()
            return
        if len(args) > 1 and representsInt(args[1]):
            num = int(args[1])
            if key in ["idea", "i"] and num >= 1 and num <= len(self.active_ideas):
                print self.active_ideas[num-1].format_citations()
            elif key in ["topic", "t"] and num >= 1 and num <= len(self.active_topics):
                print self.active_topics[num-1].format_citations()
 

    def help_show(self):
        print "Syntax \n  show CITATION-KEY: show details of a reference"
        print "  show idea|i IDEA-NUM: show details of an idea"
        print "  show topic|t TOPIC-NUM: show details of a topic"

    def do_open(self, arg):
        args = arg.split(" ")
        if len(args) == 0: 
            self.help_open()
            return
        key = args[0]
        if key in self.all_bib.citation_keys:
            r = Reference(key)
            file_path = "%s - %s.pdf"%(r.title, r.year)
            file_path = re.sub("[:?]", "", file_path)
            file_path = os.path.join(pdffile_path, file_path)
            command = "start \"\" \"%s\"" % file_path
            print command
            os.system(command)
            return
        if key in ["topic", "t"]:
            if len(args) >= 2 and representsInt(args[1]):
                topic_num = int(args[1])
                if topic_num >=1 and topic_num <= len(g_topic_list):
                    pass
                else:
                    topic_num = self.current_topic
            else:
                topic_num = self.current_topic
            t = g_topic_list[topic_num-1]
            file_path = os.path.join(topics_path, t.fname)
            command = "start \"\" \"%s\"" % file_path
            print command
            os.system(command)


    def help_open(self):
        print "Syntax \n  open CITATION-KEY: open a PDF file with specified key"
        print "  open topic|t TOPIC-NUM: open a topic file"

    def do_topic(self, arg):
        args = arg.split(" ")
        if len(args) == 0 or representsInt(args[0]) == False: 
            self.help_topic()
            return
        self.current_topic = int(args[0])
        self.balance_state()

    def help_topic(self):
        print "Syntax: topic [TOPIC-NUM]",
        print "-- set/switch current topic. Use 0 as TOPIC-NUM to make all topics visible"

    def do_list(self, arg):
        args = arg.split(" ")
        if len(args) == 0:
            return
        target = args[0]
        if target in ["topics", "topic", "t"]:
            print "Listing topics:"
            for t in g_topic_list:
                print "[%d] %s" % (g_topic_list.index(t)+1, t.title)
            if self.current_topic != 0:
                print "Current topic: %d" %(self.current_topic)
            else:
                print "You are not on any topic"
            print "You can use the topic command to set/switch current topic" 
        elif target in ["references", "reference", "ref", "r"]:
            print self.active_bib.publish()
        elif target in ["papers", "paper", "p"]:
            print self.all_bib.publish()
        elif target in ["ideas", "idea", "i"]:
            for idea in self.active_ideas:
                print "[%d] %s" % (self.active_ideas.index(idea), idea.title)
        else:
            print "Unknown argument for list command: %s" % arg

    def help_list(self):
        print "syntax:\n"
        print "    list topics|topic|t : list all unknown topics "
        print "    list references|ref|r : list all referenced papers in current topic"
        print "    list papers|paper|p : list all unknown papers"
        print "    list ideas|idea|i : list all unknown ideas in current topic"

    def do_quit(self, arg):
        sys.exit(1)

    def help_quit(self):
        print "syntax: quit",
        print "-- terminates the application"


    # shortcuts
    do_q = do_quit
    help_q = help_quit

#
# try it out
cli = CLI()
cli.cmdloop("Try typing 'help' to go further")


sys.exit(0)







