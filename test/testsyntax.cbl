       identification division.
       program-id. testsyntax.

       environment division.

       data division.
       working-storage section.
       01 a pic x.
       01 b pic 9.

       procedure division.
       main section.
           move 'x' to a
           perform sub.
           exit program.

       sub section.
       sub-start.
           if a = 'x'
               move 1 to b
               go to sub-exit.

           move 2 to b.

       sub-exit.
           exit.

       unused section.
           move 3 to b.
           exit.