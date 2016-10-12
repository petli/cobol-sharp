       identification division.
       program-id. testsyntax.

       environment division.

       data division.
       working-storage section.
       01 a pic x.
       01 b pic 9.

       procedure division.
           if b > 0
               if b > 1
                   move 'x' to a
                   go to inner-true
               else
                   go to inner-false
           else
               if b < -1
                   move 'y' to a
                   go to inner-true
               else
                   go to inner-false.

       inner-true.
           move 0 to b.
           go to finish.

       inner-false.
           move 1 to b.
           go to finish.

       finish.
           exit program.
                   