       identification division.
       program-id. testsyntax.

       environment division.

       data division.
       working-storage section.
       01 a pic x.
       01 b pic 9.

       procedure division.
       nested-loops section.
       outer-loop.
           if a > 0
               perform dec-a
               go to outer-loop
           else
               if a = 0
                   go to finish.

       inner-loop.
           if a < 0
               perform inc-a
               go to inner-loop.

           go to outer-loop.

       finish.
           exit.

       infinite section.
         perform a.

       loop.
         perform b.
         go to loop.

         perform unreached.
         exit.
