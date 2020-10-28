""" Tests of the COPASI command-line interface

:Author: Akhil Teja <akhilmteja@gmail.com>
:Date: 2020-04-16
:Copyright: 2020, Center for Reproducible Biomedical Modeling
:License: MIT
"""

try:
    from Biosimulations_utils.simulator.testing import SimulatorValidator
except ModuleNotFoundError:
    pass
try:
    import capturer # not available on all platforms
except ModuleNotFoundError:
    capturer = None
    pass

import Biosimulators_copasi
from Biosimulators_copasi import __main__

try:
    import docker
except ModuleNotFoundError:
    docker = None
    pass
import os
import numpy
import pandas
import shutil
import tempfile
import unittest
import csv


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self.dirname = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dirname)

    def test_help(self):
        with self.assertRaises(SystemExit):
            with __main__.App(argv=['--help']) as app:
                app.run()

    @unittest.skipIf(capturer is None, 'capturer not available')
    def test_version(self):
        with __main__.App(argv=['-v']) as app:
            with capturer.CaptureOutput(merged=False, relay=False) as captured:
                with self.assertRaises(SystemExit):
                    app.run()
                self.assertIn(Biosimulators_copasi.__version__, captured.stdout.get_text())
                self.assertEqual(captured.stderr.get_text(), '')

        with __main__.App(argv=['--version']) as app:
            with capturer.CaptureOutput(merged=False, relay=False) as captured:
                with self.assertRaises(SystemExit):
                    app.run()
                self.assertIn(Biosimulators_copasi.__version__, captured.stdout.get_text())
                self.assertEqual(captured.stderr.get_text(), '')

    def test_sim_short_arg_names(self):
        archive_filename = 'tests/fixtures/BIOMD0000000297.omex'
        with __main__.App(argv=['-i', archive_filename, '-o', self.dirname]) as app:
            app.run()
        self.assert_outputs_created(self.dirname)

    def test_sim_long_arg_names(self):
        archive_filename = 'tests/fixtures/BIOMD0000000297.omex'
        with __main__.App(argv=['--archive', archive_filename, '--out-dir', self.dirname]) as app:
            app.run()
        self.assert_outputs_created(self.dirname)

    @unittest.skipIf(docker is None, 'Docker not available')
    def test_build_docker_image(self):
        docker_client = docker.from_env()

        # build image
        image_repo = 'biosimulators/copasi'
        image_tag = Biosimulators_copasi.__version__
        image, _ = docker_client.images.build(
            path='.',
            dockerfile='Dockerfile',
            pull=True,
            rm=True,
        )
        image.tag(image_repo, tag='latest')
        image.tag(image_repo, tag=image_tag)

    @unittest.skipIf(docker is None, 'Docker not available')
    def test_sim_with_docker_image(self):
        docker_client = docker.from_env()

        # image config
        image_repo = 'biosimulators/copasi'
        image_tag = Biosimulators_copasi.__version__

        # setup input and output directories
        in_dir = os.path.join(self.dirname, 'in')
        out_dir = os.path.join(self.dirname, 'out')
        os.makedirs(in_dir)
        os.makedirs(out_dir)

        # create intermediate directories so that the test runner will have permissions to cleanup the results generated by
        # the docker image (running as root)
        os.makedirs(os.path.join(out_dir, 'simulation_1'))

        # copy model and simulation to temporary directory which will be mounted into container
        shutil.copyfile('tests/fixtures/BIOMD0000000297.omex',
                        os.path.join(in_dir, 'BIOMD0000000297.omex'))

        # run image
        docker_client.containers.run(
            image_repo + ':' + image_tag,
            volumes={
                in_dir: {
                    'bind': '/root/in',
                    'mode': 'ro',
                },
                out_dir: {
                    'bind': '/root/out',
                    'mode': 'rw',
                }
            },
            command=['-i', '/root/in/BIOMD0000000297.omex', '-o', '/root/out'],
            tty=True,
            remove=True)

        self.assert_outputs_created(out_dir)

    def assert_outputs_created(self, dirname, output_start_time=0., end_time=10., num_time_points=100, model_var_ids=("Trim", "Clb", "Sic", "PTrim", "PClb", "SBF", "IE", "Cdc20a", "Cdc20", "Cdh1", "Swe1", "Swe1M", "PSwe1", "PSwe1M", "Mih1a", "Mcm", "BE", "Cln", 'mass'
)):
        # print(set(os.listdir(dirname)))
        # print(set(os.listdir(os.path.join(dirname, 'simulation_1'))))
        self.assertEqual(set(os.listdir(dirname)), set(['simulation_1']))
        self.assertEqual(set(os.listdir(os.path.join(dirname, 'simulation_1'))), set(['simulation_1.csv']))

        filenames = [
            os.path.join(dirname, 'simulation_1', 'simulation_1.csv'),
        ]

        for filename in filenames:
            with open(filename, newline='') as file:
                csv.reader(file, delimiter=',')

            # check that results have expected rows and columns
            results_data_frame = pandas.read_csv(filename)

            numpy.testing.assert_array_almost_equal(
                results_data_frame['time'],
                numpy.linspace(output_start_time, end_time, num_time_points + 1),
            )

            assert set(results_data_frame.columns.to_list()) == set(list(model_var_ids) + ['time'])

    # @unittest.skipIf(docker is None, 'Docker not available')
    # def test_one_case_with_validator(self):
    #     validator = SimulatorValidator()
    #     valid_cases, case_exceptions, _ = validator.run('biosimulators/copasi', 'biosimulators.json',
    #                                                     test_case_ids=['BIOMD0000000297.omex', ])
    #     self.assertGreater(len(valid_cases), 0)
    #     self.assertEqual(case_exceptions, [])

    # @unittest.skipIf(docker is None or os.getenv('CI', '0') in ['1', 'true'], 'Test too long for continuous integration')
    # def test_with_validator(self):
    #     validator = SimulatorValidator()
    #     valid_cases, case_exceptions, _ = validator.run('biosimulators/copasi', 'biosimulators.json')
    #     self.assertGreater(len(valid_cases), 0)
    #     self.assertEqual(case_exceptions, [])
