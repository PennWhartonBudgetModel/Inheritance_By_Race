readme for inheritances.py

Files included:
main.py: This is the main program.  Options are described below.
SCF.csv.gz: This is the dataset. It is a compressed CSV file containing key variables across a large number of SCF survey
            years.
CPIU.csv:  Consumer price index.

Options that are set in main()
normalize_marrieds: Set to True divides the inheritances by two and doubles the weights to
                    approximately adjust for the fact that those households have two individuals (and hence
                    a higher chance of recieving an inheritance).
smaller_buckets: This adjusts the size of the income buckets.  Larger buckets mean larger quantiles, which are necessary
                 sometimes when there are very few observations, particularly when breaking down the distribution by race.
larger_age_buckets:  Same as "smaller_buckets", but setting the size of the bins for the age.  In some of the analyses, there
                     are not a lot of observations, so we have to make the buckets larger so that we have an adequate
                     number of observations.
race_filter: race_filter here is set to produce tables for a specific race only--set to 0 produces tables for whole population; 
             setting to 1,2,3,or 5 selects on just that race code (white, black, hispanics, other (respectively))
             smaller buckets are for.



