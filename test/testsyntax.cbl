       identification division.
       program-id. testsyntax.

       environment division.

       data division.
       working-storage section.
       01 a pic x.
       01 b pic 9.

       procedure division.
           move 'x' to a.
           initialize b.

      * Comment for paragraph main-do
      * 
       main-do.
      * Call sub
           perform sub.
           go to main-exit.
       unused.
           perform unused.
       main-exit.
           exit program.

      * Description of sub section:
      * This tests a somewhat convoluted if-else structure
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

           if x = 'z'
               move 2 to b
           else
               move 3 to b.

       sub-exit.
           exit.

       unused section.
           move 3 to b.
       unused-exit.
           exit.


      * Duplicate section with duplicate paragraphs
       unused section.
       foo.
           move 1 to a.
       foo.
           exit.
