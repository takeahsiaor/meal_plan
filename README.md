## Meal Plan

Simple Django app for planning meals, tracking recipes, and generating shopping lists. Frontend is almost entirely vibe coded because I just need something.

### Tech stack

- **Backend**: Django 6
- **Database**: SQLite (default Django config)

### Setup

1. **Create and activate a virtualenv** (if you don't already have one)
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run database migrations**
   ```bash
   cd django
   python manage.py migrate
   ```

4. **(Optional) Load base data**
   If you have fixture/JSON files for ingredients and recipes, load them or run the custom management commands you use for ingesting them.

### Running the app

From the `django` directory:

```bash
python manage.py runserver
```


### Home Server Setup Notes Specific To Me
Python was installed using the Microsoft Store, which I think is preventing me from installing different versions of Python using install exes from python.org.
The home server is on Windows 10 pro which is end of life so is not getting any updates. Whether it's because of this or not, my Microsoft store app spins up
then hangs indefinitely so I can't install any other python version through it. Without diagnosing the whole thing, I decided to just use an embeddable python 3.12.8 zip,
which required some manual steps to activate site packages and pip.

The embeddable python is at D:\Python312 and the python executable is at D:\Python312\python.exe

Once I had pip installed, I ran
`D:\Python312\python.exe -m pip install virtualenv`
to install the virtualenv library. We can't use `venv` because it's not prepackaged with the embeddable version and `virtualenv` was the easiest next choice.

I git cloned the repo to the path:
`D:\meal_plan`

To create the virtualenv for the meal_plan app, in `D:\meal_plan`, I ran:
``D:\Python312\python.exe -m virtualenv virtualenv`
The virtualenv is named "virtualenv".

I installed requirements like this:
`virtualenv\Scripts\python.exe -m pip install -r requirements.txt`

Then, once I created a `local_settings.py` file with a django secret, I'm able to run
`virtualenv\Scripts\python.exe manage.py runserver` in the django directory

Once all the initial setup is done, the helper script `django/meal_plan_start.bat` can run the server on port 9010.

I copied `meal_plan_start.bat` into `D:\Desktop` and set up a task scheduler task to execute it at startup
