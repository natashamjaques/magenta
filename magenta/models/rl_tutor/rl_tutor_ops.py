"""Helper functions to support the RLTuner and NoteRNNLoader classes."""

import os
import random

import numpy as np
import tensorflow as tf

LSTM_STATE_NAME = 'lstm'

# Number of output note classes. This is a property of the dataset.
NUM_CLASSES = 38
NUM_CLASSES_SMILE = 35

# Default batch size.
BATCH_SIZE = 128

# Music-related constants.
INITIAL_MIDI_VALUE = 48
NUM_SPECIAL_EVENTS = 2
MIN_NOTE = 48  # Inclusive
MAX_NOTE = 84  # Exclusive
TRANSPOSE_TO_KEY = 0  # C Major
DEFAULT_QPM = 80.0

# Music theory constants used in defining reward functions.
# Note that action 2 = midi note 48.
C_MAJOR_SCALE = [2, 4, 6, 7, 9, 11, 13, 14, 16, 18, 19, 21, 23, 25, 26]
C_MAJOR_KEY = [0, 1, 2, 4, 6, 7, 9, 11, 13, 14, 16, 18, 19, 21, 23, 25, 26, 28,
               30, 31, 33, 35, 37]
C_MAJOR_TONIC = 14
A_MINOR_TONIC = 23

# The number of half-steps in musical intervals, in order of dissonance
OCTAVE = 12
FIFTH = 7
THIRD = 4
SIXTH = 9
SECOND = 2
FOURTH = 5
SEVENTH = 11
HALFSTEP = 1

# Special intervals that have unique rewards
REST_INTERVAL = -1
HOLD_INTERVAL = -1.5
REST_INTERVAL_AFTER_THIRD_OR_FIFTH = -2
HOLD_INTERVAL_AFTER_THIRD_OR_FIFTH = -2.5
IN_KEY_THIRD = -3
IN_KEY_FIFTH = -5

# Indicate melody direction
ASCENDING = 1
DESCENDING = -1

# Indicate whether a melodic leap has been resolved or if another leap was made
LEAP_RESOLVED = 1
LEAP_DOUBLED = -1


class HParams(object):
  """Creates an object for passing around hyperparameter values.

  Use the parse method to overwrite the default hyperparameters with values
  passed in as a string representation of a Python dictionary mapping
  hyperparameters to values.

  Ex.
  hparams = magenta.common.HParams(batch_size=128, hidden_size=256)
  hparams.parse('{"hidden_size":512}')
  assert hparams.batch_size == 128
  assert hparams.hidden_size == 512
  """

  def __init__(self, **init_hparams):
    object.__setattr__(self, 'keyvals', init_hparams)

  def __getattr__(self, key):
    return self.keyvals.get(key)

  def __setattr__(self, key, value):
    """Returns None if key does not exist."""
    self.keyvals[key] = value

  def parse(self, string):
    new_hparams = ast.literal_eval(string)
    return HParams(**dict(self.keyvals, **new_hparams))

  def values(self):
    return self.keyvals

def default_hparams():
  """Generates the hparams used to train note rnn used in paper."""
  return HParams(use_dynamic_rnn=True,
                        batch_size=BATCH_SIZE,
                        lr=0.0002,
                        l2_reg=2.5e-5,
                        clip_norm=5,
                        initial_learning_rate=0.5,
                        decay_steps=1000,
                        decay_rate=0.85,
                        rnn_layer_sizes=[100],
                        skip_first_n_losses=32,
                        one_hot_length=NUM_CLASSES,
                        exponentially_decay_learning_rate=True)

def basic_rnn_hparams():
  """Generates the hparams used to train a basic_rnn.

  These are the hparams used in the .mag file found at 
  https://github.com/tensorflow/magenta/tree/master/magenta/models/
  melody_rnn#pre-trained
  """
  #TODO(natashajaques): ability to restore basic_rnn from any .mag 
  # file.
  return HParams(batch_size=128,
                        dropout_keep_prob=0.5,
                        clip_norm=5,
                        initial_learning_rate=0.01,
                        decay_steps=1000,
                        decay_rate=0.85,
                        rnn_layer_sizes=[512, 512],
                        skip_first_n_losses=0,
                        one_hot_length=NUM_CLASSES,
                        exponentially_decay_learning_rate=True)

def default_dqn_hparams():
  """Generates the default hparams for RLTuner DQN model."""
  return HParams(random_action_probability=0.1,
                        store_every_nth=1,
                        train_every_nth=5,
                        minibatch_size=32,
                        discount_rate=0.95,
                        max_experience=100000,
                        target_network_update_rate=0.01,
                        initial_learning_rate=0.001)


def smiles_hparams():
  """Generates the hparams used to train smiles rnn."""
  return HParams(use_dynamic_rnn=True,
                        batch_size=BATCH_SIZE,
                        lr=0.0002,
                        l2_reg=2.5e-5,
                        clip_norm=5,
                        initial_learning_rate=0.01,
                        decay_steps=1000,
                        decay_rate=0.85,
                        rnn_layer_sizes=[100],
                        one_hot_length=NUM_CLASSES_SMILE,
                        exponentially_decay_learning_rate=True)

def smiles_dqn_hparams():
  """Generates the default hparams for SmilesTutor DQN model."""
  return HParams(random_action_probability=0.1,
                store_every_nth=1,
                train_every_nth=5,
                minibatch_size=32,
                discount_rate=0.95,
                max_experience=500000,
                target_network_update_rate=0.01,
                initial_learning_rate=0.0001)

def smiles_reward_values():
  """Generates the default reward values for the smiles model."""
  return HParams(valid_length_multiplier=0,
                valid_lenth_bonus_cap=0,
                invalid_length_multiplier=0,
                sa_multiplier=2,
                logp_multiplier=3,
                ringp_multiplier=5,
                qed_multiplier=50,
                shortish_seq=-25,
                short_seq=-200,
                longish_seq=0,
                long_seq=0,
                data_scalar=1,
                any_valid_bonus=5,
                any_invalid_penalty=-5,
                end_invalid_penalty=0,
                end_valid_bonus=600,
                repeated_C_penalty=-150,
                end_valid_drug_quality_multiplier=10)

def autocorrelate(signal, lag=1):
  """Gives the correlation coefficient for the signal's correlation with itself.

  Args:
    signal: The signal on which to compute the autocorrelation. Can be a list.
    lag: The offset at which to correlate the signal with itself. E.g. if lag
      is 1, will compute the correlation between the signal and itself 1 beat
      later.
  Returns:
    Correlation coefficient.
  """
  n = len(signal)
  x = np.asarray(signal) - np.mean(signal)
  c0 = np.var(signal)

  return (x[lag:] * x[:n - lag]).sum() / float(n) / c0


def linear_annealing(n, total, p_initial, p_final):
    """Linearly interpolates a probability between p_initial and p_final.

    Current probability is based on the current step, n. Used to linearly anneal
    the exploration probability of the RLTuner.

    Args:
      n: The current step.
      total: The total number of steps that will be taken (usually the length of
        the exploration period).
      p_initial: The initial probability.
      p_final: The final probability.

    Returns:
      The current probability (between p_initial and p_final).
    """
    if n >= total:
      return p_final
    else:
      return p_initial - (n * (p_initial - p_final)) / (total)


def softmax(x):
    """Compute softmax values for each sets of scores in x."""
    e_x = np.exp(x - np.max(x))
    return e_x / e_x.sum(axis=0)

def sample_softmax(softmax):
  """Samples a note from an array of softmax probabilities.

  Tries to do this with numpy, which requires that the probabilities add to 1.0
  with extreme precision. If this fails, uses a manual implementation.

  Args:
    softmax: An array of probabilities.
  Returns:
    The index of the note that was chosen/sampled.
  """
  try:
    sample = np.argmax(np.random.multinomial(1, pvals=softmax))
    return sample
  except:  # pylint: disable=bare-except
    r = random.uniform(0, np.sum(softmax))
    upto = 0
    for i in range(len(softmax)):
      if upto + softmax[i] >= r:
        return i
      upto += softmax[i]
    tf.logging.warn("Error! sample softmax function shouldn't get here")
    print "Error! sample softmax function shouldn't get here"
    return len(softmax) - 1


def decoder(event_list, transpose_amount):
  """Translates a sequence generated by RLTuner to MonophonicMelody form.
  """
  return [e - NUM_SPECIAL_EVENTS if e < NUM_SPECIAL_EVENTS else
          e + INITIAL_MIDI_VALUE - transpose_amount for e in event_list]


def make_onehot(int_list, one_hot_length):
  """Convert each int to a one-hot vector.

  A one-hot vector is 0 everywhere except at the index equal to the
  encoded value.

  For example: 5 as a one-hot vector is [0, 0, 0, 0, 0, 1, 0, 0, 0, ...]

  Args:
    int_list: A list of ints, each of which will get a one-hot encoding.
    one_hot_length: The length of the one-hot vector to be created.
  Returns:
    A list of one-hot encodings of the ints.
  """
  return [[1.0 if j == i else 0.0 for j in xrange(one_hot_length)]
          for i in int_list]


def get_inner_scope(scope_str):
  """Takes a tensorflow scope string and finds the inner scope.

  Inner scope is one layer more internal.

  Args:
    scope_str: Tensorflow variable scope string.
  Returns:
    Scope string with outer scope stripped off.
  """
  idx = scope_str.find('/')
  return scope_str[idx + 1:]


def get_outer_scope(scope_str):
  idx = scope_str.find('/')
  return scope_str[0:idx]


def trim_variable_postfixes(scope_str):
  """Trims any extra numbers added to a tensorflow scope string.

  Necessary to align variables in graph and checkpoint

  Args:
    scope_str: Tensorflow variable scope string.
  Returns:
    Scope string with extra numbers trimmed off.
  """
  idx = scope_str.find(':')
  return scope_str[:idx]


def get_variable_names(graph, scope):
  """Finds all the variable names in a graph that begin with a given scope.

  Args:
    graph: A tensorflow graph.
    scope: A string scope.
  Returns:
    List of variables.
  """
  with graph.as_default():
    return [v.name for v in tf.all_variables() if v.name.startswith(scope)]


def get_next_file_name(directory, prefix, extension):
  """Finds next available filename in directory by appending numbers to prefix.

  E.g. If prefix is 'myfile', extenstion is '.png', and 'directory' already
  contains 'myfile.png' and 'myfile1.png', this function will return
  'myfile2.png'.

  Args:
    directory: Path to the relevant directory.
    prefix: The filename prefix to use.
    extension: String extension of the file, eg. '.mid'.
  Returns:
    String name of the file.
  """
  name = directory + '/' + prefix + '.' + extension
  i = 0
  while os.path.isfile(name):
    i += 1
    name = directory + '/' + prefix + str(i) + '.' + extension
  return name

def make_cell(hparams, note_rnn_type, state_is_tuple=False):
  """Makes a basic LSTM cell for use in the NoteRNNLoader graph.
  
  TEMPORARILY CHANGING tf.nn.rnn_cell to tf.contrib.rnn_cell"""
  cells = []
  for num_units in hparams.rnn_layer_sizes:
    if note_rnn_type == 'default':
      cell = tf.contrib.rnn.LSTMCell(
          num_units, state_is_tuple=state_is_tuple)
    else:
      cell = tf.contrib.rnn.BasicLSTMCell(
          num_units, state_is_tuple=state_is_tuple)
      cell = tf.contrib.rnn.DropoutWrapper(
          cell, output_keep_prob=hparams.dropout_keep_prob)
    cells.append(cell)

  cell = tf.contrib.rnn.MultiRNNCell(cells, state_is_tuple=state_is_tuple)
  if hparams.attn_length:
    cell = tf.contrib.rnn.AttentionCellWrapper(
        cell, hparams.attn_length, state_is_tuple=state_is_tuple)

  return cell

def log_sum_exp(xs):
  """Computes the log sum exp value of a tensor."""
  maxes = tf.reduce_max(xs, keep_dims=True)
  xs -= maxes
  return tf.squeeze(maxes, [-1]) + tf.log(tf.reduce_sum(tf.exp(xs), -1))


