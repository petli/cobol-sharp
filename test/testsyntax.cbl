       identification division.
       program-id. testsyntax.

       environment division.

       data division.
       working-storage section.
       01 a pic x.
       01 b pic 9.

       procedure division.
           move 'x' to a
       main-do.
           perform sub.
           go to main-exit.
       unused.
           perform unused.
       main-exit.
           exit program.

       sub section.
       sub-start.
           if a not = 'x'
               if a = 'y'
                   move 0 to b
                   go to sub-exit
                   perform unused
               else
                   next sentence
           else
               move 1 to b
               go to sub-exit.

           move 2 to b.
       sub-exit.
           exit.

       unused section.
           move 3 to b.
       unused-exit.
           exit.