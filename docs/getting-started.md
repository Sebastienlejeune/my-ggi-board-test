
This page explains the steps to deploy My GGI Board.  

For the moment only GitLab (either [gitlab.com](https://gitlab.com) or your own instance) is supported.
We plan to support other backends, such as [github.com](https://github.com) in the future.

[TOC]

# Overview

The set up steps are:
1. fork the [my-ggi-board repository](https://gitlab.ow2.org/ggi/my-ggi-board) in your own GitLab space.
2. create a GitLab Token, configure a CI Variable [GGI_GITLAB_TOKEN](https://docs.gitlab.com/ee/ci/variables/#add-a-cicd-variable-to-a-project)
3. run the configured pipeline, that will create:
   - GitLab **issues** that stand for the **GGI activities**,
   - appropriate **labels** for the goals, roles and progress,
   - a GitLab **issues board** for a clear overview of you current activities,
   - a static website, the **Dashboard**, to share progress and current work (in GitLab pages)
   - an updated project description, with links to you own Dashboard,
   - a nightly pipeline schedule to refresh the dashboard.



# Fork the repository

Multiple options here: you may want, for example, to use the Import feature proposed by GitLab, or fork manually.

## Fork option 1: Manual Fork

- Create an empty project on your target GitLab instance.
<img src="resources/setup_create-project.png" width="50%" height="50%">

- Clone the [my-ggi-board repository](https://gitlab.ow2.org/ggi/my-ggi-board) to your new project.

To do so, clone the my-ggi-board repository locally, and add the new project's reference to the remotes:
```
$ git clone --origin ow2-upstream https://gitlab.ow2.org/ggi/my-ggi-board.git
$ cd my-ggi-board
$ git remote add origin https://gitlab.com/<your-gitlab-space>/my-ggi-board.git
$ git push --set-upstream origin main
```

Your remotes should look like this:
```
$ git remote -v
origin  https://gitlab.com/<your-gitlab-space>/my-ggi-board.git (fetch)
origin  https://gitlab.com/<your-gitlab-space>/my-ggi-board.git (push)
ow2-upstream    https://gitlab.ow2.org/ggi/my-ggi-board.git (fetch)
ow2-upstream    https://gitlab.ow2.org/ggi/my-ggi-board.git (push)
```
**After you have pushed**, the pipeline will be triggered and will fail: this is expected, as the `GGI_GITLAB_TOKEN` variable has not been defined yet, see below.

## Fork option 2: Import Project

In your own GitLab space:
- Create a new project
- Choose: _Import project_
- Choose: _Repository by URL_
- Enter `https://gitlab.ow2.org/ggi/my-ggi-board.git`

<img src="resources/setup_import-project.png" width="50%" height="50%">

# Create your GitLab token

Two possibilities to create your [GitLab token](https://docs.gitlab.com/ee/security/token_overview.html), depending on your GitLab environment:
- use a [Project access token](https://docs.gitlab.com/ee/user/project/settings/project_access_tokens.html#project-access-tokens)
- or a [Personal access token](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html).

## Project access tokens

Create an access token (Project settings > Access Tokens) with the `api` privilege and with role `Maintainer`. Remember it, you will never see it again.
<img src="resources/setup_project-token.png" width="50%" height="50%">

## Personal access tokens

In case the instance admin has disabled the _project_ access token, you can use an _personal_ access token, although we recommend creating a dedicated account for security purposes in that case. Go to Preferences > Access Tokens and create the token from there.

<img src="resources/setup_personal-token.png" width="50%" height="50%">

# Configure and run the pipeline

Create a CI/CD env variable:
1. go to Settings > CI/CD > Variables, click <Expand>
2. add a variable named `GGI_GITLAB_TOKEN` and set the access token as the value.
3. Make it `Protected` (cannot be used in non-protected branches), `Masked` (will not be shown in Jobs logs), and (if applicable, depending on your version of GitLab) `Expanded`.

<img src="resources/setup_create-variable-1.png" width="50%" height="50%"> <img src="resources/setup_create-variable-2.png" width="50%" height="50%">

To initiate the deployment, and then update the Dashboard, you may execute the pipeline manually: Browse to _CI/CD_, _Pipelines_, and click on _Run pipeline_:

<img src="resources/setup_run-pipeline.png" width="50%" height="50%">

**Scheduled pipeline**

By default, a pipeline is scheduled every night
- you can see and update it by clicking on _Schedules_ in the _CI/CD_ menu.
- it is created if no schedule is configured
  - so if you remove it, it will reappear at next pipeline execution
  - to prevent this, you can _deactivate_ the pipeline rather than remove it.

# Result

The project description should be updated with links to :
- the static Dashboard
- the Issues Board
- the GGI Documentation

<img src="resources/project-description.png" width="75%" height="75%">


# Notes

* Prerequisites for Python are registered in `requirements.txt`. You are encouraged to create a virtual environment to execute the scripts, althought it is not required.
* GitLab CE doesn't allow to create Boards through the API.
