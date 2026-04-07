# Garmin API & Data Interpretation Guide

> Module for ZEV AI coaching knowledge base

## Data Sources

ZEV syncs data from Garmin Connect using the garminconnect Python library (133 API methods available). Data is stored as JSON blobs per day, allowing access to the full richness of Garmin's metrics.

## Additional API Endpoints Available (Not Yet Synced)

These methods are available in the garminconnect library and could be added to ZEV's sync:

### Body & Weight
- `get_body_composition(startdate, enddate)` — weight, BMI, body fat %, muscle mass, bone mass
- `get_daily_weigh_ins(date)` — individual weigh-in entries
- `get_weigh_ins(startdate, enddate)` — weight history over a range

### HRV & Readiness
- `get_hrv_data(date)` — heart rate variability metrics (RMSSD, stress balance)
- `get_training_readiness(date)` — Garmin's training readiness score
- `get_morning_training_readiness(date)` — morning-specific readiness check
- `get_training_status(date)` — Productive/Peaking/Recovery/Unproductive/Detraining/Overreaching

### Performance Metrics
- `get_max_metrics(date)` — VO2 max and related performance metrics
- `get_endurance_score(startdate, enddate)` — endurance fitness score
- `get_hill_score(startdate, enddate)` — hill/climbing fitness
- `get_race_predictions(startdate, enddate)` — predicted race times (5K, 10K, half, marathon)
- `get_lactate_threshold()` — lactate threshold heart rate and pace
- `get_running_tolerance(startdate, enddate)` — running tolerance data
- `get_fitnessage_data(date)` — calculated fitness age

### Detailed Activity Data
- `get_activity_details(activity_id)` — full activity with GPS, HR timeline, laps
- `get_activity_splits(activity_id)` — split/lap data
- `get_activity_exercise_sets(activity_id)` — strength training set data
- `get_activity_hr_in_timezones(activity_id)` — time in each HR zone
- `get_activity_weather(activity_id)` — weather during activity

### Stress & Body Battery
- `get_all_day_stress(date)` — minute-by-minute stress timeline
- `get_body_battery(startdate, enddate)` — body battery over a date range
- `get_body_battery_events(date)` — what caused battery drain/charge events

### Other
- `get_hydration_data(date)` — water intake tracking
- `get_respiration_data(date)` — detailed respiration rate
- `get_spo2_data(date)` — blood oxygen readings
- `get_floors(date)` — floors climbed detail
- `get_intensity_minutes_data(date)` — intensity minutes breakdown
- `get_personal_record()` — user's personal records (fastest 5K, longest run, etc.)
- `get_goals(status)` — user's configured fitness goals

## Daily Stats (`get_stats`)

The main daily summary. Key fields in the JSON:

### Activity Metrics
- `totalSteps` — total steps for the day
- `dailyStepGoal` — the user's configured step goal
- `totalDistanceMeters` — total distance walked/run in meters
- `activeKilocalories` — calories burned through activity
- `totalKilocalories` — total calories including BMR
- `floorsAscended` — floors climbed
- `moderateIntensityMinutes` — minutes at 100-120% of resting HR
- `vigorousIntensityMinutes` — minutes above 120% of resting HR

### Heart Rate
- `restingHeartRate` — resting HR for the day (key fitness indicator)
- `maxHeartRate` — highest HR recorded
- `minHeartRate` — lowest HR recorded
- `lastSevenDaysAvgRestingHeartRate` — 7-day rolling average RHR

### Stress & Recovery
- `averageStressLevel` — average stress score (0-100, HRV-derived)
- `highStressDuration` — seconds spent in high stress
- `mediumStressDuration` — seconds in medium stress
- `lowStressDuration` — seconds in low stress
- `restStressDuration` — seconds in rest/recovery state
- `stressPercentage` — percentage of day spent stressed

### Body Battery
- `bodyBatteryHighestValue` — peak body battery (0-100)
- `bodyBatteryLowestValue` — lowest point
- `bodyBatteryMostRecentValue` — current/latest reading
- `bodyBatteryChargedValue` — how much it charged (usually during sleep)
- `bodyBatteryDrainedValue` — how much it drained (during activity/stress)
- `bodyBatteryAtWakeTime` — body battery when you woke up

### Blood Oxygen
- `averageSpo2` — average SpO2 percentage
- `lowestSpo2` — lowest reading (often during deep sleep)
- `latestSpo2` — most recent reading

### Respiration
- `avgWakingRespirationValue` — average breaths per minute while awake

## Heart Rate Records (`get_heart_rates`)

Per-day heart rate summary:
- `restingHeartRate` — the day's resting HR
- `maxHeartRate` — peak HR
- `minHeartRate` — lowest HR
- `lastSevenDaysAvgRestingHeartRate` — 7-day average

**Coaching implications:**
- Resting HR trending down over weeks = improving fitness
- Sudden elevation of 5-10+ bpm = possible illness, overtraining, or stress
- Max HR during exercise helps validate training zone accuracy

## Sleep Records (`get_sleep_data`)

Detailed sleep breakdown:
- `sleepTimeSeconds` — total sleep duration
- `deepSleepSeconds` — time in deep sleep (physical recovery)
- `lightSleepSeconds` — time in light sleep
- `remSleepSeconds` — time in REM (mental recovery, motor learning)
- `awakeSleepSeconds` — time awake during the night
- `avgHeartRate` — average HR during sleep
- `averageSpO2Value` — blood oxygen during sleep
- `avgSleepStress` — stress level during sleep (should be low)
- `averageRespirationValue` — breathing rate during sleep
- `sleepScoreFeedback` — Garmin's feedback (e.g., "NEGATIVE_NOT_ENOUGH_REM")
- `sleepScoreInsight` — insight (e.g., "NEGATIVE_STRESSFUL_DAY")

**Coaching implications:**
- Deep sleep under 45 minutes = impaired physical recovery
- REM under 60 minutes = impaired mental recovery
- Average sleep HR significantly above resting HR = poor sleep quality
- Sleep SpO2 consistently below 92% = worth mentioning to GP (possible sleep apnea)

## Activities (`get_activities_by_date`)

Individual workout/activity records:
- `activityName` — user-given or auto-detected name
- `activityType` → `typeKey` — standardized type (running, cycling, strength_training, walking, meditation, hiking, swimming)
- `duration` — total duration in seconds
- `movingDuration` — active time (excludes rest periods)
- `distance` — distance in meters
- `calories` — estimated calories burned
- `averageHR` — average heart rate during activity
- `maxHR` — peak heart rate
- `avgSpeed` / `maxSpeed` — in m/s

**Coaching implications:**
- Compare averageHR across similar activities to track fitness improvements
- Duration trends show consistency
- Distance + duration = pace (for running/cycling)
- Calorie estimates are rough — use for trends, not absolute numbers

## Key Metric Interpretation for Coaching

### Body Battery Decision Framework
- **75-100 at wake:** Fully recovered. Hard training day.
- **50-75 at wake:** Moderate recovery. Train as planned, monitor how you feel.
- **25-50 at wake:** Under-recovered. Light session or technique work.
- **Below 25:** Depleted. Rest day or very light movement.

### Stress Score Context
- Stress is derived from HRV, not self-reported feelings
- High stress during exercise is normal and expected
- High stress at rest is the concern — indicates sympathetic nervous system activation
- Average daily stress above 40-50 consistently suggests chronic stress

### VO2 Max Trends
- Garmin estimates VO2 max from running pace + heart rate data
- Accuracy is ±2-3 ml/kg/min for recreational athletes
- More reliable as a trend indicator than an absolute number
- Drops after illness, detraining, or during high fatigue
- Improves with consistent zone 2 training

### Training Load & Status
- **Productive:** Fitness is improving. Keep doing what you're doing.
- **Peaking:** High fitness + reduced load. Ideal for race week.
- **Recovery:** Low training load. Body is recovering.
- **Unproductive:** Training hard but fitness isn't improving. Check recovery.
- **Detraining:** Fitness declining from reduced activity.
- **Overreaching:** Training load too high relative to fitness. Risk of injury/burnout.

### What Metrics to Average vs Look at Daily
- **Average over 7+ days:** Resting HR, stress, steps, sleep duration, Body Battery wake value
- **Look at daily:** Activity-specific data, sleep breakdown, workout HR
- **Track monthly trends:** VO2 max, resting HR, training load balance

### Data Quirks to Know
- Sleep data may be missing if the watch wasn't worn overnight
- Body Battery resets at midnight — a late-night workout can show confusing patterns
- Steps can include arm movements incorrectly (e.g., pushing a stroller)
- Stress readings during eating can spike due to digestion
- SpO2 readings are least accurate with cold hands or tight watch bands
