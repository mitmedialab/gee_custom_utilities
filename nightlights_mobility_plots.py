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



def AvgAndChange(dataf, columnList, periodLength, baselines):
    dataf_out = dataf
    for index, row in dataf.iterrows():
        dfDate = index
        rollingSet = dataf[(dataf.index > (dfDate - datetime.timedelta(days=(periodLength + 1)))) &
                        (dataf.index < (dfDate + datetime.timedelta(days=1)))]
        for entry, baseline in zip(columnList, baselines):
            rollingAvg = rollingSet[entry].mean()
            dataf_out.loc[index,'30 Day Average of ' + entry] = rollingAvg
            dataf_out.loc[index, 'Rolling Average Percent Change of ' + entry] = (rollingAvg - baseline)/baseline
            dataf_out.loc[index, 'Percent Change of ' + entry] = (row[entry] - baseline)/baseline
            
    return dataf_out


# %% Nightlights
df = pd.read_csv('/home/jackreid/Downloads/temp/dailyCountyAveragesTable.csv')

for index, row in df.iterrows():
    df.loc[index, 'Date'] = datetime.datetime.strptime(row['system:index'][0:10], '%Y-%m-%d')
    
df.set_index('Date', inplace=True)


df_jan2020 = df[(df.index > datetime.datetime(2020,1,2)) &
                (df.index < datetime.datetime(2020,2,7))]

nightlight_baseline = [df_jan2020['mean'].mean(), df_jan2020['median'].mean()]

df = AvgAndChange(df, ['mean', 'median'], 15, nightlight_baseline)

# for index, row in df.iterrows():
#     dfDate = index
#     rollingSet = df[(df.index > (dfDate - datetime.timedelta(days=31))) &
#                     (df.index < (dfDate + datetime.timedelta(days=1)))]
#     rollingAvg = rollingSet['mean'].mean()
#     df.loc[index,'30 Day Average'] = rollingAvg
#     df.loc[index, 'nightlightsPercentChange'] = (rollingAvg - nightlight_baseline)/nightlight_baseline


dfPlot = df.loc[df.index > datetime.datetime(2020,2,14)]

# %% Mobility

dfMob = pd.read_csv('/home/jackreid/Downloads/temp/google_mobility/santaClara_county_full.csv')

for index, row in dfMob.iterrows():
    dfMob.loc[index, 'Date'] = datetime.datetime.strptime(row['date'], '%Y-%m-%d')
    mobArray = np.asarray([row['transit_stations_percent_change_from_baseline'],
                row['workplaces_percent_change_from_baseline'],
                row['retail_and_recreation_percent_change_from_baseline']])
    dfMob.loc[index, 'AvgMobility'] = np.average(mobArray)
    
dfMob.set_index('Date', inplace=True)

dfMob = AvgAndChange(dfMob, ['AvgMobility'], 30, [1])

dfMobPlot = dfMob.loc[dfMob.index > datetime.datetime(2020,2,14)]

# %% Plot - MEAN

fig = plt.figure() # Create matplotlib figure

ax = fig.add_subplot(111) # Create matplotlib axes
ax2 = ax.twinx() # Create another axes that shares the same x-axis as ax.


lns1 = dfPlot['Rolling Average Percent Change of mean'].plot(kind='line', color='orange', ax=ax, style='--')
lns4 = dfMobPlot['30 Day Average of AvgMobility'].plot(kind='line', color='blue', ax=ax2)

ax.set_xlabel("Date", size=24)

# # plt.xlim(1963,2020)
# # ax.set_ylim(0,0.06)

# # # ax.set_ylim(0,0.06)
# # # ax2.set_ylim(0,140)
ax.set_ylabel('Relative Change in County-Wide Nightlights', size=16)
ax2.set_ylabel('Relatie Change in Google Mobility Data', size=16)
# # # plt.xticks(rotation=45, ha="right")

lines, labels = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax2.legend(lines + lines2, ["Nightlights", "Mobility"], loc=9)
plt.title("Mean Nightlights Comparison")

# %% Plot- MEDIAN

fig2 = plt.figure() # Create matplotlib figure

ax3 = fig2.add_subplot(111) # Create matplotlib axes
ax4 = ax3.twinx() # Create another axes that shares the same x-axis as ax.


lns2 = dfPlot['Rolling Average Percent Change of median'].plot(kind='line', color='orange', ax=ax3, style='--')
lns3 = dfMobPlot['30 Day Average of AvgMobility'].plot(kind='line', color='blue', ax=ax4)

ax3.set_xlabel("Date", size=24)

# # plt.xlim(1963,2020)
# # ax.set_ylim(0,0.06)

# # ax.set_ylim(0,0.06)
# # # ax2.set_ylim(0,140)
ax3.set_ylabel('Relative Change in County-Wide Nightlights', size=16)
ax4.set_ylabel('Relatie Change in Google Mobility Data', size=16)
# # # plt.xticks(rotation=45, ha="right")

lines3, labels3 = ax3.get_legend_handles_labels()
lines4, labels4 = ax4.get_legend_handles_labels()
ax3.legend(lines3 + lines4, ["Nightlights", "Mobility"], loc=9)
plt.title("Median Nightlights Comparison")
