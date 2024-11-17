#!/usr/bin/python3
# ######################################################################
# Copyright (c) 2022 Boris Baldassari, Nico Toussaint and others
#
# This program and the accompanying materials are made
# available under the terms of the Eclipse Public License 2.0
# which is available at https://www.eclipse.org/legal/epl-2.0/
#
# SPDX-License-Identifier: EPL-2.0
######################################################################

# This script:
# - reads the metadata defined in the `conf` directory,
# - retrieves information from the gitlab project,
# - updates the static website with new information and plots


import gitlab
import json
import pandas as pd
import re
import glob, os
from fileinput import FileInput
from datetime import date
from collections import OrderedDict
import tldextract
import urllib.parse

# Define some variables.

file_conf = 'conf/ggi_deployment.json'
file_meta = 'conf/ggi_activities_metadata.json'
file_json_out = 'ggi_activities_full.json'

# Define regexps
# Identify tasks in description:
re_tasks = re.compile(r"^\s*- \[(?P<is_completed>.)\] (?P<task>.+)$")
# Identify tasks in description:
re_activity_id = re.compile(r"^Activity ID: \[(GGI-A-\d\d)\]\(.+\).$")
# Identify sections for workflow parsing.
re_section = re.compile(r"^### (?P<section>.*?)\s*$")
re_subsection = re.compile(r"^#### (?P<subsection>.*?)\s*$")

def extract_workflow(activity_desc):
    paragraphs = activity_desc.split('\n')
    content_t = 'Introduction'
    content = OrderedDict()
    content = {content_t: []}
    a_id = ""
    for p in paragraphs:
        activity_id_match = re_activity_id.match(p)
        if activity_id_match:
            a_id = activity_id_match.group(1)
            continue
        match_section = re.search(re_section, p)
        if match_section:
            content_t = match_section.group('section')
            content[content_t] = []
        else:
            content[content_t].append(p)
    subsection = 'Default'
    workflow = {subsection: []}
    # Parse the scorecard section.
    tasks = []
    if 'Scorecard' in content:
        for p in content['Scorecard']:
            match_subsection = re.search(re_subsection, p)
            if match_subsection:
                subsection = match_subsection.group('subsection')
                workflow[subsection] = []
            elif p != '':
                workflow[subsection].append(p)
                # Now identify tasks
                match_tasks = re.search(re_tasks, p)
                if match_tasks:
                    is_completed = match_tasks.group('is_completed')
                    is_completed = True if is_completed == 'x' else False
                    task = match_tasks.group('task')
                    tasks.append({'is_completed': is_completed, 'task': task})
    # Remove first element (useless html stuff)
    del workflow['Default']
    # Remove last two elements (useless html stuff too)
    del workflow[list(workflow)[-1]][-1]
    del workflow[list(workflow)[-1]][-1]
    return a_id, content['Description'], workflow, tasks

#
# Read metadata for activities and deployment options.
#

print(f"# Reading deployment options from {file_conf}.")
with open(file_conf, 'r', encoding='utf-8') as f:
    conf = json.load(f)

# Determine GitLab server URL and Project name
# From Environment variable if available
# From configuration file otherwise

if 'CI_SERVER_URL' in os.environ:
    GGI_GITLAB_URL = os.environ['CI_SERVER_URL']
    print("- Use GitLab URL from environment variable")
else:
    print("- Use GitLab URL from configuration file")
    GGI_GITLAB_URL = conf['gitlab_url']

if 'CI_PROJECT_PATH' in os.environ:
    GGI_GITLAB_PROJECT = os.environ['CI_PROJECT_PATH']
    print("- Use GitLab Project from environment variable")
else:
    print("- Use GitLab URL from configuration file")
    GGI_GITLAB_PROJECT = conf['gitlab_project']

if 'GGI_GITLAB_TOKEN' in os.environ:
    print("- Using ggi_gitlab_token from env var.")
else:
    print("- Cannot find env var GGI_GITLAB_TOKEN. Please set it and re-run me.")
    exit(1)

if 'CI_PAGES_URL' in os.environ:
    GGI_PAGES_URL = os.environ['CI_PAGES_URL']
    print("- Using GGI_PAGES_URL from environment variable.")
else:
    print("- Cannot find an env var for GGI_PAGES_URL. Computing it from conf.")
    pieces = tldextract.extract(GGI_GITLAB_URL)
    GGI_PAGES_URL = 'https://' + GGI_GITLAB_PROJECT.split('/')[0] + \
        "." + pieces.domain + ".io/" + GGI_GITLAB_PROJECT.split('/')[-1]

GGI_URL = urllib.parse.urljoin(GGI_GITLAB_URL, GGI_GITLAB_PROJECT)
GGI_ACTIVITIES_URL = os.path.join(GGI_URL+'/', '-/boards')

print(f"\n# Connection to GitLab at {GGI_GITLAB_URL} - {GGI_GITLAB_PROJECT}.")
gl = gitlab.Gitlab(url=GGI_GITLAB_URL, per_page=50, private_token=os.environ['GGI_GITLAB_TOKEN'])
project = gl.projects.get(GGI_GITLAB_PROJECT)

print("# Fetching issues..")
gl_issues = project.issues.list(state='opened', all=True)

# Define columns for recorded dataframes.
issues = []
issues_cols = ['issue_id', 'activity_id', 'state', 'title', 'labels',
               'updated_at', 'url', 'desc', 'workflow', 'tasks_total', 'tasks_done']

tasks = []
tasks_cols = ['issue_id', 'state', 'task']

hist = []
hist_cols = ['time', 'issue_id', 'event_id', 'type', 'author', 'action', 'url']

count = 1
workflow = {}
tasks = []
activities_dataset = []

for i in gl_issues:
    desc = i.description
    paragraphs = desc.split('\n\n')
    lines = desc.split('\n')
    a_id, description, workflow, a_tasks = extract_workflow(desc)
    for t in a_tasks:
        tasks.append([a_id,
                      'completed' if t['is_completed'] else 'open',
                      t['task']])
    short_desc = '\n'.join(description)
    tasks_total = len(a_tasks)
    tasks_done = len( [ t for t in a_tasks if t['is_completed'] ] )
    issues.append([i.iid, a_id, i.state, i.title, ','.join(i.labels),
                   i.updated_at, i.web_url, short_desc, workflow, tasks_total, tasks_done])

    # Used for the activities table dataset
    status = "Not started"
    if tasks_done > 0:
        status = "In progress"
        if tasks_done == tasks_total:
            status = "Completed"

    activities_dataset.append([a_id, status, i.title, tasks_done, tasks_total])

    # Retrieve information about labels.
    for n in i.resourcelabelevents.list():
        event = i.resourcelabelevents.get(n.id)
        n_type = 'label'
        label = n.label['name'] if n.label else ''
        n_action = f"{n.action} {label}"
        line = [n.created_at, i.iid,
                n.id, n_type, n.user['username'], 
                n_action, i.web_url]
        hist.append(line)

    print(f"- {i.iid} - {a_id} - {i.title} - {i.web_url} - {i.updated_at}.")
        
    # Remove these lines when dev/debug is over
    if count == 30:
        break
    else:
        count += 1

# Convert lists to dataframes
issues = pd.DataFrame(issues, columns=issues_cols)
tasks = pd.DataFrame(tasks, columns=tasks_cols)
hist = pd.DataFrame(hist, columns=hist_cols)

# Identify activities depending on their progress
issues_not_started = issues.loc[issues['labels'].str.contains(conf['progress_labels']['not_started']),]
issues_in_progress = issues.loc[issues['labels'].str.contains(conf['progress_labels']['in_progress']),]
issues_done = issues.loc[issues['labels'].str.contains(conf['progress_labels']['done']),]

# Print all issues, tasks and events to CSV file
print("\n# Writing issues and history to files.")
issues.to_csv('web/content/includes/issues.csv',
              columns=['issue_id', 'activity_id', 'state', 'title', 'labels',
               'updated_at', 'url', 'tasks_total', 'tasks_done'], index=False)
hist.to_csv('web/content/includes/labels_hist.csv', index=False)
tasks.to_csv('web/content/includes/tasks.csv', index=False)

# Generate list of current activities
print("\n# Writing issues.") 

for local_id, activity_id, activity_date, title, url, desc, workflow, tasks_done, tasks_total in zip(
        issues['issue_id'],
        issues['activity_id'],
        issues['updated_at'],
        issues['title'],
        issues['url'],
        issues['desc'],
        issues['workflow'],
        issues['tasks_done'],
        issues['tasks_total']):
    print(f" {local_id}, {activity_id}, {title}, {url}")

    my_issue = []

    my_issue.append('---')
    my_issue.append(f'title: {title}')
    my_issue.append(f'date: {activity_date}')
    my_issue.append('layout: default')
    my_issue.append('---')
    
    my_issue.append(f"Link to Issue: <a href='{url}' class='w3-text-grey' style='float:right'>[ {activity_id} ]</a>\n\n")
    my_issue.append(f"Tasks: {tasks_done} done / {tasks_total} total.")
    if tasks_total > 0:
        p = int(tasks_done) * 100 // int(tasks_total)
        my_issue.append(f'  <div class="w3-light-grey w3-round">')
        my_issue.append(f'    <div class="w3-container w3-blue w3-round" style="width:{p}%">{p}%</div>')
        my_issue.append(f'  </div><br />')
    else:
        my_issue.append(f'  <br /><br />')
    my_workflow = "\n"
    for subsection in workflow:
        my_workflow += f'**{subsection}**\n\n'
        my_workflow += '\n'.join(workflow[subsection])
        my_workflow += '\n\n'
    my_issue.append(f"{my_workflow}")

    filename = f'web/content/scorecards/activity_{activity_id}.md'
    with open(filename, 'w') as f:
        f.write('\n'.join(my_issue))
    
# Generate data points for the dashboard
ggi_data_all_activities = f'[{issues_not_started.shape[0]}, {issues_in_progress.shape[0]}, {issues_done.shape[0]}]'
with open('web/content/includes/ggi_data_all_activities.inc', 'w') as f:
    f.write(ggi_data_all_activities)

# Generate data points for the dashboard - goals - done
done_stats = [
    issues_done['labels'].str.contains('Usage').sum(),
    issues_done['labels'].str.contains('Trust').sum(),
    issues_done['labels'].str.contains('Culture').sum(),
    issues_done['labels'].str.contains('Engagement').sum(),
    issues_done['labels'].str.contains('Strategy').sum()
]
with open('web/content/includes/ggi_data_goals_done.inc', 'w') as f:
    f.write(str(done_stats))

# Generate data points for the dashboard - goals - in_progress
in_progress_stats = [
    issues_in_progress['labels'].str.contains('Usage').sum(),
    issues_in_progress['labels'].str.contains('Trust').sum(),
    issues_in_progress['labels'].str.contains('Culture').sum(),
    issues_in_progress['labels'].str.contains('Engagement').sum(),
    issues_in_progress['labels'].str.contains('Strategy').sum()
]
with open('web/content/includes/ggi_data_goals_in_progress.inc', 'w') as f:
    f.write(str(in_progress_stats))

# Generate data points for the dashboard - goals - not_started
not_started_stats = [
    issues_not_started['labels'].str.contains('Usage').sum(),
    issues_not_started['labels'].str.contains('Trust').sum(),
    issues_not_started['labels'].str.contains('Culture').sum(),
    issues_not_started['labels'].str.contains('Engagement').sum(),
    issues_not_started['labels'].str.contains('Strategy').sum()
]
with open('web/content/includes/ggi_data_goals_not_started.inc', 'w') as f:
    f.write(str(not_started_stats))

# Generate activities basic statistics, with links to be used from home page.
activities_stats = f'Identified {issues.shape[0]} activities overall.\n'
activities_stats += f'* {issues_not_started.shape[0]} are <span class="w3-tag w3-light-grey">not_started</span>\n'
activities_stats += f'* {issues_in_progress.shape[0]} are <span class="w3-tag w3-light-grey">in_progress</span>\n'
activities_stats += f'* {issues_done.shape[0]} are <span class="w3-tag w3-light-grey">done</span>\n'
with open('web/content/includes/activities_stats_dashboard.inc', 'w') as f:
    f.write(activities_stats)

with open('web/content/includes/activities.js.inc', 'w') as f:
    f.write(str(activities_dataset))

# Empty (or not) the initialisation banner text in index.
if issues_not_started.shape[0] < 25:
    with open('web/content/includes/initialisation.inc', 'w') as f:
        f.write('')

# TODO : remove all unused anymore .inc

#
# Setup website
#

#
# Replace 
#
print("\n# Replacing keywords in static website.")

# List of strings to be replaced.
print("\n# List of keywords and values:")
keywords = {
    '[GGI_URL]': GGI_URL,
    '[GGI_PAGES_URL]': GGI_PAGES_URL,
    '[GGI_ACTIVITIES_URL]': GGI_ACTIVITIES_URL,
    '[GGI_CURRENT_DATE]': str(date.today())
}
[ print(f"- {k} {keywords[k]}") for k in keywords.keys() ]

# Replace keywords in md files.
def update_keywords(file_in, keywords):
    occurrences = []
    for keyword in keywords:
        for line in FileInput(file_in, inplace=1, backup='.bak'):
            if keyword in line:
                occurrences.append(f'- Changing "{keyword}" to "{keywords[keyword]}" in {file_in}.')
                line = line.replace(keyword, keywords[keyword])
            print(line, end='')
    [ print(o) for o in occurrences ]
            
print("\n# Replacing keywords in files.")
update_keywords('web/config.toml', keywords)
update_keywords('web/content/includes/initialisation.inc', keywords)
update_keywords('web/content/scorecards/_index.md', keywords)
#update_keywords('README.md', keywords)
files = glob.glob("web/content/*.md")
files_ = [ f for f in files if os.path.isfile(f) ]
for file in files_:
    update_keywords(file, keywords)

print("Done.")
