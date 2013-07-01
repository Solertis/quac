'Various mathematical routines.'

# Copyright (c) 2012-2013 Los Alamos National Security, LLC, and others.

import datetime
import numbers

import numpy as np

import testable
import time_


### Misc ###

def is_power_2(i):
   '''Return True if i is a positive power of two, false otherwise. This
      relies on a common bit-twiddling trick; see e.g.
      <http://stackoverflow.com/a/600306/396038>. For example:

      >>> is_power_2(0)
      False
      >>> is_power_2(1)
      True
      >>> is_power_2(3)
      False
      >>> is_power_2(4)
      True'''
   assert (isinstance(i, numbers.Integral))
   assert (i >= 0)
   return (i > 0) and ((i & (i - 1)) == 0)


### Vector similarity ###

class Date_Vector(np.ndarray):
   '''NumPy array of daily values that knows its start date and a few related
      operations. For example:

      >>> a = Date_Vector('2013-06-02', np.arange(2, 7))
      >>> a
      Date_Vector([2, 3, 4, 5, 6])
      >>> a.first_day
      datetime.date(2013, 6, 2)
      >>> a.last_day
      datetime.date(2013, 6, 6)

      Notes:

      1. You must manually create and pass in a standard NumPy array; this is
         so you can use all the fancy constructors (in addition to being much
         easier to implement).

      2. The first day argument can either be a datetime.date object or a
         string in ISO 8601 format.

      3. You can pass None for the first day, but nothing will work right
         until you set the first_day attribute.'''

   # There is some weirdness here because NumPy arrays are weird. See
   # <http://docs.scipy.org/doc/numpy/user/basics.subclassing.html>. We follow
   # the "slightly more realistic example" pattern.

   def __new__(class_, first_day, input_array):
      o = np.asarray(input_array).view(class_)
      o.first_day = first_day
      return o

   def __array_finalize__(self, o):
      if (o is None):
         return
      self.first_day = getattr(o, 'first_day', None)

   @property
   def first_day(self):
      return self._first_day
   @first_day.setter
   def first_day(self, x):
      self._first_day = time_.dateify(x)

   @property
   def last_day(self):
      if (self._first_day is None):
         return None
      else:
         return self._first_day + datetime.timedelta(days=(len(self) - 1))

   def resize(self, first_day, last_day):
      '''Return a copy of myself with new bounds first_day and last_day; data
         are either trimmed or extended with zeroes, as appropriate. If either
         bound is None, use the existing bound. If the new bounds cross,
         return None. The returned vector will share data with the source
         vector if shrinking only.

         For example:

         >>> a = Date_Vector('2013-06-02', np.arange(2, 7))
         >>> a
         Date_Vector([2, 3, 4, 5, 6])

         # shrink
         >>> b = a.resize('2013-06-03', None)
         >>> np.may_share_memory(a, b)
         True
         >>> b
         Date_Vector([3, 4, 5, 6])
         >>> (b.first_day, b.last_day)
         (datetime.date(2013, 6, 3), datetime.date(2013, 6, 6))
         >>> a.resize(None, '2013-06-04')
         Date_Vector([2, 3, 4])
         >>> a.resize('2013-06-03', '2013-06-04')
         Date_Vector([3, 4])
         >>> a.resize(None, None)
         Date_Vector([2, 3, 4, 5, 6])
         >>> a.resize('2013-06-06', None)
         Date_Vector([6])
         >>> a.resize(None, '2013-06-02')
         Date_Vector([2])
         >>> a.resize('2013-06-07', None)  # None
         >>> a.resize(None, '2013-06-01')  # None

         # grow
         >>> b = a.resize('2013-06-01', '2013-06-07')
         >>> b
         Date_Vector([0, 2, 3, 4, 5, 6, 0])
         >>> (b.first_day, b.last_day)
         (datetime.date(2013, 6, 1), datetime.date(2013, 6, 7))
         >>> np.may_share_memory(a, b)
         False
         >>> a.resize('2013-06-01', None)
         Date_Vector([0, 2, 3, 4, 5, 6])
         >>> a.resize(None, '2013-06-07')
         Date_Vector([2, 3, 4, 5, 6, 0])

         # grow and shrink
         >>> b = a.resize('2013-06-01', '2013-06-05')
         >>> b
         Date_Vector([0, 2, 3, 4, 5])
         >>> np.may_share_memory(a, b)
         False
         >>> a.resize('2013-06-03', '2013-06-07')
         Date_Vector([3, 4, 5, 6, 0])

         # no-op gives a copy, but it's shallow
         >>> b = a.resize(None, None)
         >>> b
         Date_Vector([2, 3, 4, 5, 6])
         >>> b is a
         False
         >>> np.may_share_memory(a, b)
         True'''
      # clean up new bounds
      fd_new = time_.dateify(first_day) or self.first_day
      ld_new = time_.dateify(last_day) or self.last_day
      # if they're empty, return None
      if (max(fd_new, self.first_day) > min(ld_new, self.last_day)):
         return None
      # how many elements to add and remove from the start?
      delta_start = time_.days_diff(fd_new, self.first_day)
      trim_start = max(0, delta_start)
      add_start = max(0, -delta_start)
      # how many elements to add and remove from the end?
      delta_end = time_.days_diff(self.last_day, ld_new)
      trim_end = max(0, delta_end)
      add_end = max(0, -delta_end)
      # Do it!
      if (add_start == 0 and add_end == 0):
         # If shrinking, don't use hstack(); this avoids copying data, which
         # favors speed over memory. The caller can do a deep copy if this is
         # a problem.
         return Date_Vector(fd_new, self[trim_start:len(self) - trim_end])
      else:
         return Date_Vector(fd_new,
                            np.hstack([np.zeros(add_start, dtype=self.dtype),
                                       self[trim_start:len(self) - trim_end],
                                       np.zeros(add_end, dtype=self.dtype)]))

# def similarity(a, a_start, b, b_start,
#                mask=None, mask_start=None, metric=cosine):
#    '''Return the similarity, in the range [0,1], of ``Date_Vector``\ s a and
#       b. mask is a boolean validity Date_Vector; mask[i] is True if a[i] and
#       b[i] are valid data, False otherwise. All three vectors are NumPy
#       arrays. metric '''
#    assert (mask is not None), 'mask is None not implemented'


testable.register('')
