"""CPU checks for failures that must stop a candidate memory preflight."""
import unittest

import torch

from preflight_training import validate_gradients


class PreflightGradientTests(unittest.TestCase):
    def parameter(self, gradient):
        parameter = torch.nn.Parameter(torch.ones(2, device='cpu'))
        if gradient is not None:
            parameter.grad = torch.tensor(gradient, dtype=parameter.dtype)
        return parameter

    def test_fresh_lora_can_have_zero_a_gradients(self):
        parameters = [('lora_A', self.parameter([0, 0])),
                      ('lora_B', self.parameter([1, -1]))]
        self.assertEqual(validate_gradients(parameters, torch),
                         {'parameters_with_gradients': 2, 'parameters_with_nonzero_gradients': 1})

    def test_missing_branch_gradient_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'no gradient'):
            validate_gradients([('present', self.parameter([1, 1])),
                                ('disconnected', self.parameter(None))], torch)

    def test_nonfinite_gradient_fails(self):
        for value in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, 'Nonfinite'):
                validate_gradients([('bad', self.parameter([1, value]))], torch)

    def test_no_learning_signal_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'All.*zero'):
            validate_gradients([('zero', self.parameter([0, 0]))], torch)
        with self.assertRaisesRegex(RuntimeError, 'No trainable'):
            validate_gradients([], torch)


if __name__ == '__main__':
    unittest.main()
