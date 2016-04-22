#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This module is part of the Clemson ACM Auto Grader

Copyright (c) 2016, Robert Underwood
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

This module provides utilities that allow for enumerating through student
submissions.
"""

import json
import os
import logging
import multiprocessing
from autograder.source import build, clean, clone, update
from autograder.report import reports
from autograder.test import run, score, parse
from autograder.controller import enviroment
from autograder.discover import users, tests, reporters
LOGGER = logging.getLogger(__name__)

def grade(settings):
    """
    Grade all of the projects
    """
    LOGGER.info("Preparing environment")
    enviroment.prepare_enviroment(settings)
    LOGGER.info("Determining users")
    students = users.enumerate_students(settings)
    LOGGER.info("Determining tests")
    test_cases = tests.enumerate_tests(settings)
    LOGGER.info("Determining reports")
    report_tasks = reporters.enumerate_reports(settings)

    old_results = load_old_results(settings, students)

    results = {}
    with multiprocessing.Pool(processes=settings['project']['multiprocess']) as pool:
        jobs = [(settings, student, old_results.get(student['username']), test_cases) \
                for student in students]
        ret = pool.starmap(grade_student, jobs)
        results = {i[0]:i[1] for i in ret}
        pool.starmap(reports.reports, [(report, results, students) for report in report_tasks])

    with open(settings['project']['name'] + ".json", "w") as results_file:
        json.dump(results, results_file)

def load_old_results(settings, students):
    """
    load the old results file or a dictionary of all students if it doesn't exists
    """
    try:
        with open(settings['project']['name'] + ".json") as results_file:
            old_results = json.load(results_file)
    except FileNotFoundError:
        old_results = {student['username']:None for student in students}
    return old_results

def grade_student(settings, student, old_results, test_cases):
    """
    Grade student a specific students work
    """
    if not os.path.exists(student['directory']):
        LOGGER.info("Downloading student %s", student['username'])
        clone.clone(settings, student)
        updated = True
    else:
        LOGGER.info("Updating student %s", student['username'])
        clean.clean(settings, student)
        updated = update.update(settings, student)

    if settings['update']['forced'] or updated or (old_results is None):
        LOGGER.info("Running tests for student %s", student['username'])
        build.build(settings, student)
        results = []
        for test in test_cases:
            result = run_test(settings, student, test)
            results.append(result)
    else:
        LOGGER.info("No update for student %s", student['username'])
        results = old_results

    return (student['username'], results)


def run_test(settings, student, test):
    """
    Run a test on a students work
    """
    if settings['clean']['method'] != "docker":
        clean.clean(settings, student)
    if settings['build']['method'] != "docker":
        build.build(settings, student)
    output = run.run(settings, student, test)
    result = parse.parse(output, test)
    points = score.score(result, output, test)
    return {
        "output": output,
        "results": result,
        "points": points
    }
