#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct  4 12:26:42 2022

@author: jackreid
"""

import csv
import datetime
import pandas as pd
# import dateutil
import matplotlib.pyplot as plt
import numpy as np


rollingAvgPeriod = 14

def AvgAndChange(dataf, columnList, periodLength, baselines):
    dataf_out = dataf
    for index, row in dataf.iterrows():
        dfDate = index
        rollingSet = dataf[(dataf.index > (dfDate - datetime.timedelta(days=(periodLength + 1)))) &
                        (dataf.index < (dfDate + datetime.timedelta(days=1)))]
        for entry, baseline in zip(columnList, baselines):
            rollingAvg = rollingSet[entry].mean()
            dataf_out.loc[index,'Rolling Average of ' + entry] = rollingAvg
            dataf_out.loc[index, 'Rolling Average Percent Change of ' + entry] = (rollingAvg - baseline)/baseline
            dataf_out.loc[index, 'Percent Change of ' + entry] = (row[entry] - baseline)/baseline

    return dataf_out


# %% Nightlights
df = pd.read_csv('/home/jackreid/Documents/School/Research/Space_Enabled/Code/Nightlights-Mobility/dailyEastPaloAltoAveragesTable.csv')

for index, row in df.iterrows():
    df.loc[index, 'Date'] = datetime.datetime.strptime(row['system:index'][0:10], '%Y-%m-%d')
    
# df.set_index('Date', inplace=True)

censusTracts = df['NAME'].unique();

dfTractList = [];
for tract in censusTracts:
    dfTractList.append(df[df['NAME'] == tract])
    
dfPlotList = [];
for dfTract in dfTractList:
    dfTract.set_index('Date', inplace=True)

    df_jan2020 = dfTract[(dfTract.index > datetime.datetime(2020,1,2)) &
                    (dfTract.index < datetime.datetime(2020,2,7))]
    
    nightlight_baseline = [df_jan2020['mean'].mean(), df_jan2020['median'].mean()]
    
    dfTract = AvgAndChange(dfTract, ['mean', 'median'], rollingAvgPeriod, nightlight_baseline)
    
    dfPlotList.append(dfTract.loc[dfTract.index > datetime.datetime(2020,2,14)])

# %% Mobility

dfMob = pd.read_csv('/home/jackreid/Documents/School/Research/Space_Enabled/Code/Nightlights-Mobility/replica/replica-trends-east-palo-alto-ca-oct-6-2022 (1)/east-palo-alto--ca_spend-by-merchant-location_in-person-spend_tract_-full-week_from_week_of_dec-30--2019_to_week_of_sep-26--2022.csv')

dfMobTractList = [];
for tract in censusTracts:
    dfMobTractList.append(dfMob[(dfMob['tract'].str[0:4] == str(tract))])

dfMobPlotList = [];
for dfTract in dfMobTractList:
    
    for index, row in dfTract.iterrows():
        dfTract.loc[index, 'Date'] = datetime.datetime.strptime(row['week_starting'], '%m-%d-%Y')
        # mobArray = np.asarray([row['grocery_stores_spend_fullweek'],
        #             row['workplaces_percent_change_from_baseline'],
        #             row['retail_and_recreation_percent_change_from_baseline']])
        # dfMob.loc[index, 'AvgMobility'] = np.average(mobArray)
        dfTract.loc[index, 'Transactions'] = row['restaurants_bars_spend_fullweek']
    dfTract.set_index('Date', inplace=True)
    df_jan2020 = dfTract[(dfTract.index > datetime.datetime(2020,1,2)) &
                    (dfTract.index < datetime.datetime(2020,2,7))]
    mob_baseline = [df_jan2020['Transactions'].mean()]
    dfTract = AvgAndChange(dfTract, ['Transactions'], rollingAvgPeriod, mob_baseline)
    dfMobPlotList.append(dfTract.loc[dfTract.index > datetime.datetime(2020,2,14)])

# %% Plot - MEAN

fig, axs = plt.subplots(2,2)

increm = 0
for nightlight, transact, ax, tract in zip(dfPlotList, dfMobPlotList, axs.flat, censusTracts):
    ax2 = ax.twinx() # Create another axes that shares the same x-axis as ax.
    lns1 = nightlight['Rolling Average Percent Change of median'].plot(kind='line', color='orange', ax=ax, style='--')
    lns4 = transact['Percent Change of Transactions'].plot(kind='line', color='blue', ax=ax2)
    ax.set_xlabel("Date", size=24)
    ax.set_ylim(-1,1)
    ax2.set_ylim(-1,1)

# # # plt.xticks(rotation=45, ha="right")
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    if increm == 0:
        ax2.legend(lines + lines2, ["Nightlights", "Replica Spend"], loc=9)
        ax.set_ylabel('Nightlights', size=16)
    if increm == 1:
        ax2.set_ylabel('Replica Restaurant/Bars Spend', size=16)
    
    ax.label_outer()
    plt.title('Tract ' + str(tract))
    increm += 1

# # %% Plot- MEDIAN

# fig2 = plt.figure() # Create matplotlib figure

# ax3 = fig2.add_subplot(111) # Create matplotlib axes
# ax4 = ax3.twinx() # Create another axes that shares the same x-axis as ax.


# lns2 = dfPlot['Percent Change of median'].plot(kind='line', color='orange', ax=ax3, style='--')
# lns3 = dfMobPlot['Rolling Average Percent Change of Transactions'].plot(kind='line', color='blue', ax=ax4)

# ax3.set_xlabel("Date", size=24)

# # # plt.xlim(1963,2020)
# # # ax.set_ylim(0,0.06)

# # # # ax.set_ylim(0,0.06)
# # # # ax2.set_ylim(0,140)
# ax3.set_ylabel('Relative Change in County-Wide Nightlights', size=16)
# ax4.set_ylabel('Relatie Change in Google Mobility Data', size=16)
# # # # plt.xticks(rotation=45, ha="right")

# lines3, labels3 = ax3.get_legend_handles_labels()
# lines4, labels4 = ax4.get_legend_handles_labels()
# ax3.legend(lines3 + lines4, ["Nightlights", "Mobility"], loc=9)
# plt.title("Median Nightlights Comparison")
