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

"""

"""
import time
import urllib.parse
import requests

from ggi_deploy import *
from github import Github, GithubException
from github import Auth


def main():
    """
    Main GITHUB.
    """
    args = parse_args()

    print("* Using GitHub backend.")
    metadata, params, init_scorecard = retrieve_env()
    setup_github(metadata, params, init_scorecard, args)

    print("\nDone.")

def create_github_label(repo, new_label, label_args):
    existing_labels = {label.name for label in repo.get_labels()}

    """
    Creates a set of labels in the GitHub project.
    """
    if new_label in existing_labels:
        print(f" Ignore label: {new_label}")
    else:
        print(f" Create label: {new_label}")
        name = label_args['name']
        color = label_args['color'].replace("#","")
        repo.create_label(name, color)

# Fonction pour obtenir l'ID du dépôt ou de l'organisation
def get_owner_id(owner, repo, gh_token):
    url = 'https://api.github.com/graphql'

    headers = {
        'Authorization': f'bearer {gh_token}',
        'Content-Type': 'application/json'
    }

    query = f"""
        {{
          user(login: "{owner}") {{
            id
          }}
          organization(login: "{owner}") {{
            id
          }}
        }}
        """
    response = requests.post(url, headers=headers, json={'query': query})
    if response.status_code == 200:
        data = response.json()
        if 'data' in data:
            if 'user' in data['data'] and data['data']['user'] is not None:
                return data['data']['user']['id']
            elif 'organization' in data['data'] and data['data']['organization'] is not None:
                return data['data']['organization']['next_global_id']
            else:
                raise Exception("Failed to retrieve user or organization ID.")
        else:
            raise Exception("Failed to retrieve user or organization ID: 'data' field is missing.")
    else:
        raise Exception(f"Query failed to run by returning code of {response.status_code}. {response.text}")

# Fonction pour créer un projet
def create_project(owner_id, gh_token):
    url = 'https://api.github.com/graphql'

    # Mutation GraphQL pour créer un projet
    query = """
    mutation {
      createProjectV2(input: {
        ownerId: "REPO_ORG_ID",
        title: "Goals Board"
      }) {
        projectV2 {
          id
          title
        }
      }
    }
    """

    headers = {
        'Authorization': f'bearer {gh_token}',
        'Content-Type': 'application/json'
    }

    query_with_owner = query.replace("REPO_ORG_ID", owner_id)
    response = requests.post(url, headers=headers, json={'query': query_with_owner})
    if response.status_code == 200:
        data = response.json()
        return data['data']['createProjectV2']['projectV2']
    else:
        raise Exception(
            f"Mutation failed to run by returning code of {response.status_code}. {response.text}")

def setup_github(metadata, params: dict, init_scorecard, args: dict):
    """
    Executes the following deployment sequence on a GitHub instance:
    * Reads github-specific variables.
    * Connect to GitHub
    * Create labels & activities
    * Create Goals board
    * Create schedule for pipeline
    """

    # Get conf: Token
    if 'GGI_GITHUB_TOKEN' in os.environ:
        print("- Using token from env var 'GGI_GITHUB_TOKEN'")
        params['github_token'] = os.environ['GGI_GITHUB_TOKEN']
    else:
        print("- Cannot find env var GGI_GITHUB_TOKEN. Please set it and re-run me.")
        exit(1)
    auth = Auth.Token(params['github_token'])

    # Get conf: URL
    public_github="https://github.com"
    if 'GGI_GITHUB_URL' in os.environ:
        params['github_url'] = os.environ['GGI_GITHUB_URL']
        print("- Using URL from env var 'GGI_GITHUB_URL'")
    elif 'github_url' in params and params['github_url'] != None:
        print("- Using URL from configuration file")
    else:
        params['github_url'] = public_github
        print("- Using default public URL")

    if params['github_url'].startswith(public_github):
        # Public Web Github
        print("- Using public GitHub instance.")
        g = Github(auth=auth)
    else:
        print(f"- Using GitHub on-premise host {params['github_url']} ")
        # Github Enterprise with custom hostname
        params['github_url'] = f"{params['github_url']}/api/v3"
        g = Github(auth=auth, base_url=params['github_url'])

    # Gett conf: Project
    if 'GGI_GITHUB_PROJECT' in os.environ:
        params['github_project'] = os.environ['GGI_GITHUB_PROJECT']
        print("- Using Project from env var 'GGI_GITHUB_PROJECT'")
    elif 'github_project' in params:
        print(f"- Using Project from configuration file")
    else:
        print("I need a project (org + repo), e.g. ospo-alliance/" +
              "my-ggi-board. Exiting.")
        exit(1)


    params['github_repo_url'] = urllib.parse.urljoin(params['github_url'], params['github_project'])
    params['github_activities_url'] = params['github_repo_url'] + '/projects'

    print("Configuration:")
    print("URL     : " + params['github_url'])
    print("Project : " + params['github_project'])
    print("Full URL: " + params['github_repo_url'])


    headers = {
        "Authorization": f"Bearer {params['github_token']}",
        "Accept": "application/vnd.github.inertia-preview+json"  # Needed for project board access
    }

    # Connecting to the GitHub instance.

    print(f"\n# Retrieving project from GitHub at {params['github_repo_url']}.")
    repo = g.get_repo(params['github_project'])

    # Update current project description with Website URL
    if args.opt_projdesc:
        print("\n# Update Project description")
        ggi_activities_url = params['github_activities_url']

        repo_fullname = os.getenv("GITHUB_REPOSITORY", "unknown/repo")  # "username/repository-name"
        repo_owner = os.getenv("GITHUB_REPOSITORY_OWNER", "unknown")  # "username"
        repo_name = repo_fullname.split("/")[-1]
        github_pages_url = f"https://{repo_owner}.github.io/{repo_name}/"

        desc = (
            'Here you will find your dashboard: ' + github_pages_url + ' and the issues board: ' + ggi_activities_url + ' with all activities describing the local GGI'
        )
        print(f"nNew description:\n<<<---------\n{desc}\n--------->>>\n")

        # Update the repository description
        repo.edit(description=desc, homepage="https://ospo-alliance.org/")

    #
    # Create labels & activities
    #
    if args.opt_activities:

        # Create labels.
        print("\n# Manage labels")

        # Create role labels if needed
        print("\n Roles labels")
        for label, colour in metadata['roles'].items():
            create_github_label(repo, label, {'name': label, 'color': colour})

        # Create labels for activity tracking
        print("\n Progress labels")
        for name, label in params['progress_labels'].items():
            create_github_label(repo, label, {'name': label, 'color': 'ed9121'})

        # Create goal labels if needed
        print("\n Goal labels")
        for goal in metadata['goals']:
            create_github_label(repo, goal['name'],
                                {'name': goal['name'], 'color': goal['colour']})

        # Create issues with their associated labels.
        print("\n# Create activities.")
        # First test the existence of Activities Issues:
        #   if at least one Issue is found bearing one Goal label,
        #   consider that all Issues exist and do not add any.
        open_issues = repo.get_issues(state='open')
        if open_issues.totalCount > 0:
            print("Ignore, Issues already exist")
        else:
            for activity in metadata['activities']:
                progress_label = params['progress_labels']['not_started']
                if args.opt_random:
                    # Choix aléatoire parmi les étiquettes de progression valides
                    progress_idx = random.choice(list(params['progress_labels']) + ['none'])
                    if progress_idx != 'none':
                        progress_label = params['progress_labels'][progress_idx]
                labels = [activity['goal']] + activity['roles']
                if progress_label != '':
                    labels = labels + [progress_label]

                print(f"  - Issue: {activity['name']:<60} Labels: {labels}")
                # Création de l'issue
                try:
                    issue = repo.create_issue(
                        title=activity['name'],
                        body=extract_sections(args, init_scorecard, activity),
                        labels=labels
                    )
                    time.sleep(2)
                except GithubException as e:
                    print(f"Status: {e.status}, Data: {e.data}")

    # Create Goals board
    if args.opt_board:
        # TODO : check why graphQL API does not work
        create_project_graphql(params)
        # TODO : check why : 410 {"message": "Projects are disabled for this repository"
        #create_project_pygithub(params)

    # Close the connection.
    g.close()


def create_project_pygithub(params):
    access_token = params['github_token']

    from github import Github
    from github.GithubException import GithubException

    g = Github(access_token)

    try:
        repo = g.get_repo("Sebastienlejeune/my-ggi-board")
        project_name = "Goals Project"
        project_exists = False

        for project in repo.get_projects():
            if project.name == project_name:
                project_exists = True
                existing_project = project
                break

        if not project_exists:
            new_project = repo.create_project(name=project_name, body="Project to track goals.")
            print(f"Created new project: {new_project.name}")
        else:
            print("Project already exists.")

        metadata_goals = [{'name': 'Goal 1'}, {'name': 'Goal 2'}]
        project = new_project if not project_exists else existing_project

        existing_columns = list(project.get_columns())
        for goal in metadata_goals:
            column_exists = any(column.name == goal['name'] for column in existing_columns)
            if not column_exists:
                new_column = project.create_column(goal['name'])
                print(f"Created new column: {new_column.name}")
            else:
                print(f"Column already exists for goal: {goal['name']}")

    except GithubException as e:
        if e.status == 410:
            print(e)
        else:
            print(f"An error occurred: {e}")


def create_project_graphql(params):
    print(f"\n# Create Goals board: {ggi_board_name}")
    # Your GitHub token and the repo details
    access_token = params['github_token']
    headers = {'Authorization': f'bearer {access_token}'}
    graphql_url = 'https://api.github.com/graphql'
    repo_owner = 'Sebastienlejeune'
    repo_name = 'my-ggi-board'
    # Query to check for an existing project
    query = """
        query ($repo_owner: String!, $repo_name: String!, $project_name: String!) {
          repository(owner: $repo_owner, name: $repo_name) {
            projects(search: $project_name, first: 10) {
              nodes {
                id
                name
              }
            }
          }
        }
        """
    variables = {
        "repo_owner": repo_owner,
        "repo_name": repo_name,
        "project_name": "Goals Project"
    }
    response = requests.post(graphql_url, json={'query': query, 'variables': variables}, headers=headers)
    projects_data = json.loads(response.text)
    # Check if project exists and find its ID
    project_id = None
    for project in projects_data['data']['repository']['projects']['nodes']:
        if project['name'] == variables['project_name']:
            project_id = project['id']
            break
    # If the project does not exist, create it
    if not project_id:
        mutation_create_project = """
                mutation ($project_name: String!) {
                  createProject(input: {name: $project_name, ownerId: $owner_id}) {
                    project {
                      id
                      name
                    }
                  }
                }
            """

        # Fetching the repository ID for ownerId in mutation
        repo_id_query = """
            query ($repo_owner: String!, $repo_name: String!) {
              repository(owner: $repo_owner, name: $repo_name) {
                id
              }
            }
            """

        variables = {
            "repo_owner": repo_owner,
            "repo_name": repo_name
        }
        repo_response = requests.post(graphql_url, json={'query': repo_id_query, 'variables': variables},
                                      headers=headers)
        repo_id = json.loads(repo_response.text)['data']['repository']['id']
        print("repo ID = " + repo_id)
        # Creating the project
        create_variables = {
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "project_name": "Goals Project",
            "owner_id": "MDQ6VXNlcjYxNDk2OTEx"
        }

        #create_variables['repository_owner_id'] = repo_id
        #response_data = get_repo_id(headers)
        #print(response_data)

        project_response = requests.post(graphql_url,
                                         json={'query': mutation_create_project, 'variables': create_variables},
                                         headers=headers)
        project_data = json.loads(project_response.text)
        # Print the entire response to inspect what GitHub API returned
        print("GitHub API response:", project_data)

        # Check if 'errors' key is present in the response
        if 'errors' in project_data:
            print("Errors returned from the GitHub API:", project_data['errors'])
        else:
            project_id = project_data['data']['createProject']['project']['id']
            print(f"Created new project: {project_data['data']['createProject']['project']['name']}")
    # Example goals to create columns for, and assuming project_id is now available
    goals = ['Goal 1', 'Goal 2']
    for goal in goals:
        # Mutation to add a column
        mutation_add_column = """
            mutation ($project_id: ID!, $column_name: String!) {
              addProjectColumn(input: {projectId: $project_id, name: $column_name}) {
                projectColumn {
                  id
                  name
                }
              }
            }
            """
        column_variables = {
            "project_id": project_id,
            "column_name": goal
        }
        column_response = requests.post(graphql_url,
                                        json={'query': mutation_add_column, 'variables': column_variables},
                                        headers=headers)
        column_data = json.loads(column_response.text)
        print(f"Created column: {column_data['data']['addProjectColumn']['projectColumn']['name']}")

def get_repo_id(headers):
    graphql_url = 'https://api.github.com/graphql'

    # GraphQL query to get repository owner ID
    query = """
    query ($repo_owner: String!, $repo_name: String!) {
      repository(owner: $repo_owner, name: $repo_name) {
        owner {
          id
          login
          __typename
        }
      }
    }
    """

    # Variables for the query
    variables = {
        "repo_owner": "Sebastienlejeune",  # e.g., 'octocat'
        "repo_name": "my-ggi-board"  # e.g., 'Hello-World'
    }

    # Make the request to GitHub GraphQL API
    response = requests.post(graphql_url, json={'query': query, 'variables': variables}, headers=headers)
    response_data = json.loads(response.text)
    return response_data


if __name__ == '__main__':
    main()
