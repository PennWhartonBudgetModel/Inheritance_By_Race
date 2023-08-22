'''
produce some tables according to data from 2001-2019 raw SCF inheritance variables
Table 1: P(receiving inheritance Last Year)
Table 2: Avg. inheritance (conditional on having received any inheritance)
Table 3: Avg. inheritance (unconditional)

Groupings: age & income deciles
FOR EACH TABLE U WILL BE PRESENTING THE MEDIAN OF THE VALUES ACROSS ALL SURVEY YEARS 

'''

import pandas as pd 
import numpy as np 
import os
from pandas._libs.lib import is_integer


def main():
    """
    the master function
    """
    inflation_index = pd.read_csv("CPIU.csv")
    df = pd.read_csv('SCF.csv.gz')
    df = df[df.Year>=2001]
    # use bulletin (adjusted) weights, not weights from raw dataset
    grouping_vars = ['Year', 'AgeGroup', 'IncomeGroup']
    
    df = calculate_inheritance_last_year(df, normalize_marrieds=False)
    
    #race_filter here is set to produce tables for a specific race only--set to 0 produces tables for whole population; 
    # setting to 1,2,3,or 5 selects on just that race code (white, black, hispanics, other (respectively))
    # smaller buckets are for 
    df = calculate_groups(df, race_filter=0, smaller_buckets=True, larger_age_buckets=True)
    df = all_ages_all_incomes(df)

    df, probabilities = calculate_probabilities(df)
    conditionalavgs = calculate_averages_conditional(df)
    df, averages = calculate_average_inheritance(df)
    averages = pd.merge(averages, conditionalavgs, on=grouping_vars, how = "outer")

    averages = inflate_asset_values(averages, ['AvgInheritanceLastYear', 'AvgInheritanceLastYear_Conditional'], inflation_index)
    final_vars = ['GroupWeight', 'P_ReceivedInheritanceLastYear', 'AvgInheritanceLastYear', 'AvgInheritanceLastYear_Conditional']
    final_vars_only = pd.merge(averages, probabilities, on=grouping_vars)[grouping_vars + final_vars]
    final_vars_only['AvgInheritanceLastYear_Conditional'] = final_vars_only['AvgInheritanceLastYear_Conditional'].fillna(0)

    medians = get_median_by_year(final_vars_only, key_vars=final_vars)
    # os.chdir('C:\Inheritances\Tables')
    filename = 'inheritancetables_5YearGroups_marriageFix_Repro.xlsx'
    # save excel
    print(medians)
    write_workbook(medians, final_vars_only, filename)


def calculate_inheritance_last_year(df, normalize_marrieds=True):
    '''
    Function to construct "InheritanceLastYear" variables
    '''
    survey_years = list(df.Year.unique())
    inheritance_vars = ['InheritanceOrGift1', 'InheritanceOrGift2', 'InheritanceOrGift3']
    df['InheritanceLastYear'] = 0

    for year in survey_years:
        subset = df[df.Year==year]
        if year==2001:
            target_year = 1995
        elif year==2004:
            target_year = 2000
        elif (year==2007) | (year==2010):
            target_year = 2005
        elif (year==2013) | (year==2016):
            target_year = 2010
        elif year==2019:
            target_year = 2015
        else:
            raise Exception("year out of range")

        for var in inheritance_vars:
            subset.loc[(subset['YearOf'+var]==target_year), 'InheritanceLastYear'] = subset['InheritanceLastYear'] + subset['ValueOf'+var]
            #if year == 2007:
            #   subset.loc[(subset['YearOf'+var]==2005), 'InheritanceLastYear'] = subset['InheritanceLastYear'] + subset['ValueOf'+var]
        
        df.loc[(df.Year==year), 'InheritanceLastYear'] = subset.InheritanceLastYear
    
    if normalize_marrieds:
        df.loc[(df.Married==1), 'InheritanceLastYear'] = df.InheritanceLastYear/2
        df.loc[(df.Married==1), 'Weight'] = df.Weight*2
        # also include all income / wealth variables that will be used
        df.loc[(df.Married==1), 'NetWorth'] = df.NetWorth/2
        df.loc[(df.Married==1), 'Income_Wages'] = df.Income_Wages/2
        df.loc[(df.Married==1), 'Income_BusinessAndFarm'] = df.Income_BusinessAndFarm/2

    return df

def calculate_groups(df, reset_ages=True, race_filter=0, smaller_buckets=False, larger_age_buckets=False):
    """
    to calculate age and income groups (income deciles calculated WITHIN each age group )
    according to WAGE INCOME
    """
    ## STEP ONE IS TO CALCULATE AGE AND INCOME GROUPS
    # NOTE: USE Age_HeadOfHousehold for this calculation

    #first grouping is by Year
    years = list(df.Year.unique())
    # set ages to year capturing 5-year inheritance span. 
    if reset_ages:
        df.loc[(df['Year']==2001), 'Age_HeadOfHousehold'] = df['Age_HeadOfHousehold'] - 6
        df.loc[(df['Year']==2004), 'Age_HeadOfHousehold'] = df['Age_HeadOfHousehold'] - 4
        df.loc[(df['Year']==2007), 'Age_HeadOfHousehold'] = df['Age_HeadOfHousehold'] - 2
        df.loc[(df['Year']==2010), 'Age_HeadOfHousehold'] = df['Age_HeadOfHousehold'] - 5
        df.loc[(df['Year']==2013), 'Age_HeadOfHousehold'] = df['Age_HeadOfHousehold'] - 3
        df.loc[(df['Year']==2016), 'Age_HeadOfHousehold'] = df['Age_HeadOfHousehold'] - 6
        df.loc[(df['Year']==2019), 'Age_HeadOfHousehold'] = df['Age_HeadOfHousehold'] - 4

    df['AgeGroup'] = np.floor((df.Age_HeadOfHousehold-6)/10).astype(int)
    df.loc[(df['AgeGroup']<1), 'AgeGroup'] = 1
    if larger_age_buckets:
        df.loc[df.Age_HeadOfHousehold>=75, 'AgeGroup']= 4
        df.loc[df.Age_HeadOfHousehold<75, 'AgeGroup'] = 3
        df.loc[df.Age_HeadOfHousehold<55, 'AgeGroup'] = 2
        df.loc[df.Age_HeadOfHousehold<35, 'AgeGroup'] = 1

    agegroups = list(df.AgeGroup.unique())
    df['IncomeGroup_Overall'] = 0
    df['IncomeGroup'] = 0
    # define income Variable
    df['Income'] = df.Income_Wages + df.Income_BusinessAndFarm
    # need to create IncomeGroup within each age group
    for year in years:
        yrsubset = df[df.Year==year]
        yrsubset['IncomeGroup_Overall'] = weighted_qcut(yrsubset.Income, yrsubset.Weight, 20, labels=False)
        yrsubset.loc[(yrsubset.IncomeGroup_Overall==19), 'IncomeGroup_Overall'] = 50
        if smaller_buckets:
            yrsubset['IncomeGroup_Overall'] = weighted_qcut(yrsubset.Income, yrsubset.Weight, 4, labels=False)
        #yrsubset['Top2_Overall'] = weighted_qcut(yrsubset.Income, yrsubset.Weight, 50, labels=False)
        #distinguish top 5% from the rest, but code 95% and under from 0-9
        #yrsubset.loc[(yrsubset.Top2_Overall==49), 'IncomeGroup_Overall'] = 100
        #assign IncomeGroups by Year to original dataframe
        df.loc[(df.Year==year), 'IncomeGroup_Overall'] = yrsubset.IncomeGroup_Overall
        for agegroup in agegroups:
            age_subset = yrsubset[yrsubset.AgeGroup==agegroup]
            age_subset['IncomeGroup'] = weighted_qcut(age_subset.Income, age_subset.Weight, 20, labels=False)
            age_subset.loc[(age_subset.IncomeGroup==19), 'IncomeGroup'] = 50
            if smaller_buckets:
                age_subset['IncomeGroup'] = weighted_qcut(age_subset.Income, age_subset.Weight, 4, labels=False)
            #age_subset['Top2'] = weighted_qcut(age_subset.Income, age_subset.Weight, 50, labels=False)
            
            #age_subset.loc[(age_subset.Top2==49), 'IncomeGroup'] = 100
            df.loc[(df.Year==year) & (df.AgeGroup==agegroup), 'IncomeGroup'] = age_subset.IncomeGroup 
    
    if smaller_buckets==False:
        for groupvar in ['IncomeGroup_Overall', 'IncomeGroup']:
            df[groupvar] = np.floor(df[groupvar]/2).astype(int)
            df.loc[(df[groupvar]==25), groupvar] = 10
            #df.loc[(df[groupvar]==50), groupvar] = 11
    if race_filter>0:
        df = df[df.Race_Detailed==race_filter]

    return df

def calculate_probabilities(df):
    """
    function to calculate the probabilities of receiving an inheritance last year
    REMINDER THIS IS CONDITIONED ON DECILE IN AGE / INCOME GROUP (within each survey year)
    """
    grouping_vars         = ['Year', 'AgeGroup', 'IncomeGroup']
    overall_grouping_vars = ['Year', 'AgeGroup', 'IncomeGroup_Overall']
    vars_to_calculate     = ['GroupWeight', 'GroupInheritanceLY']

    df['HasInheritanceLY'] = 0
    df.loc[(df.InheritanceLastYear>0),'HasInheritanceLY'] = 1
    df['ThoseWithInheritanceLastYear'] = df.HasInheritanceLY * df.Weight
    
    #calculate group totals, and probability of receiving an inheritance last year (by group)
    df['GroupWeight'] = df.groupby(grouping_vars)['Weight'].transform('sum')
    df['GroupInheritanceLY'] = df.groupby(grouping_vars)['ThoseWithInheritanceLastYear'].transform('sum')
    
    summ = df[grouping_vars + vars_to_calculate].drop_duplicates(grouping_vars)
    summ = summ.sort_values(by=grouping_vars, ascending=[False, True, True])

    summ['P_ReceivedInheritanceLastYear'] = summ.GroupInheritanceLY / summ.GroupWeight
    
    return df, summ

def calculate_averages_conditional(df):
    '''
    By age/income group, calculate the averate inheritance received (ever) 
    And average inheritance received last year
    Plus same values, conditioned on inheritance
    '''
    grouping_vars     = ['Year', 'AgeGroup', 'IncomeGroup']
    intermediate_vars = ['GroupWeight', 'GroupInheritanceLastYear']
    vars_produced     = ['AvgInheritanceLastYear_Conditional']
    
    conditional = df[df.InheritanceLastYear>0]
    
    conditional['WeightedInheritanceLastYear'] = conditional.InheritanceLastYear * conditional.Weight
    conditional['GroupWeight'] = conditional.groupby(grouping_vars)['Weight'].transform('sum')
    conditional['GroupInheritanceLastYear']    = conditional.groupby(grouping_vars)['WeightedInheritanceLastYear'].transform('sum')
   
    avgs = conditional.drop_duplicates(grouping_vars)[grouping_vars + intermediate_vars]

    # create df to calculate these values conditional on Receiving any InheritanceLY
    avgs['AvgInheritanceLastYear_Conditional']      = avgs.GroupInheritanceLastYear / avgs.GroupWeight
    
    avgs = avgs.sort_values(by=grouping_vars, ascending=[False, True, True])[grouping_vars + vars_produced]

    return avgs

def calculate_average_inheritance(df):
    '''
    By age/income group, calculate the averate inheritance received (ever) 
    And average inheritance received last year
    Plus same values, conditioned on inheritance
    '''
    grouping_vars     = ['Year', 'AgeGroup', 'IncomeGroup']
    intermediate_vars = ['GroupWeight', 'GroupInheritanceLastYear']
    vars_produced     = ['AvgInheritanceLastYear']

    df['WeightedInheritanceLastYear'] = df.InheritanceLastYear * df.Weight
    df['GroupInheritanceLastYear']    = df.groupby(grouping_vars)['WeightedInheritanceLastYear'].transform('sum')
   
    avgs = df.drop_duplicates(grouping_vars)[grouping_vars + intermediate_vars]

    # create df to calculate these values conditional on Receiving any InheritanceLY
    avgs['AvgInheritanceLastYear']      = avgs.GroupInheritanceLastYear / avgs.GroupWeight
    
    avgs = avgs.sort_values(by=grouping_vars, ascending=[False, True, True])[grouping_vars + vars_produced]

    return df, avgs

def all_ages_all_incomes(df):
    '''
    takes in the df, 
    summ (the concatenated df grouped by the grouping vars)
    grouping vars
    '''
    all_ages = df.copy()
    all_ages['IncomeGroup'] = all_ages.IncomeGroup_Overall
    all_ages['AgeGroup'] = 99

    df = df.append(all_ages)

    all_incomes = df.copy()
    all_incomes['IncomeGroup'] = 99
    df = df.append(all_incomes)
    
    return df

def inflate_asset_values(df, vars_to_inflate, inflation_index, yearindex='Year'):
    '''
    pass in dataframe and variables to inflate
    '''
    baseindex = inflation_index[inflation_index.Year==2020]['Index'].iloc[0]

    for year in df[yearindex].unique():
        yrdf = df[df.Year==year]
        index = inflation_index[inflation_index.Year==year]['Index'].iloc[0]

        for asset in vars_to_inflate:
            yrdf[asset+'Index'] = 0
            yrdf[asset+ 'Index'] = yrdf[asset]/index
            df.loc[(df.Year==year), asset+'Index'] = yrdf[asset + 'Index'] 

    #deflate all by retrieving current year index
    
    nominal_renames = {}
    inflated_renames = {}
    for asset in vars_to_inflate:
        df[asset + 'Inflated'] = df[asset+'Index'] * baseindex
        df.drop(columns = [asset+'Index'], inplace=True)
        nominal_renames[asset] = asset + 'Nominal'
        inflated_renames[asset + 'Inflated'] = asset
    
    df.rename(columns = nominal_renames, inplace=True)
    df.rename(columns = inflated_renames, inplace=True)
        
    return df

def get_median_by_year(df, key_vars):
    '''
    provide dataframe and variables from which it will pull the median across years
    '''
    created_vars = []
    for var in key_vars:
        df['Median' + var] = df.groupby(['AgeGroup', 'IncomeGroup'])[var].transform('median')
        created_vars.append('Median'+var)

    medians = df.drop_duplicates(['AgeGroup', 'IncomeGroup'])
    medians = medians[['AgeGroup', 'IncomeGroup'] + created_vars]

    df.drop(columns=created_vars, inplace=True)
    
    return medians

def write_workbook(medians, fulldf, filename):
    '''
    writes to excel workbook, medians as first sheet then values for all years after
    '''
    agegroup_labels = {
        1: "Under 26",
        2: "26-35",
        3: "36-45",
        4: "46-55",
        5: "56-65",
        6: "66-75",
        7: "76-85",
        8: "86-95",
        99: "All Ages"
    }
    if len(fulldf.AgeGroup.unique())<6:
        agegroup_labels = {
            1: "Under 35",
            2: "35-54",
            3: "55-74",
            4: "75 +",
            99: "All Ages"
        }
    medians.replace({'AgeGroup': agegroup_labels}, inplace=True)
    fulldf.replace({'AgeGroup': agegroup_labels}, inplace=True)

    spreadsheet = pd.ExcelWriter(filename, engine='xlsxwriter')
    medians.to_excel(spreadsheet, sheet_name='Medians', index=None)

    for year in fulldf.Year.unique():
        df2 = fulldf[fulldf.Year==year]
        df2.to_excel(spreadsheet, sheet_name=str(year), index=None)
    
    spreadsheet.save()

def weighted_qcut(values, weights, q, **kwargs):
    'Return weighted quantile cuts from a given series, values.'
    if is_integer(q):
        quantiles = np.linspace(0, 1, q + 1)
    else:
        quantiles = q
    order = weights.iloc[values.argsort()].cumsum()
    bins = pd.cut(order / order.iloc[-1], quantiles, **kwargs)
    return bins.sort_index()


pd.set_option("display.max_rows", 100000000, "display.max_columns", 100000000)
main()