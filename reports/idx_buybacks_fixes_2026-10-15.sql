-- idx_buybacks corrections from the 2026-10-15 audit against IDX filings
-- Run inside one transaction; review each block first.
begin;

-- 1. Field corrections (each value is stated in the cited filing)
-- PRDA 2026-08-20..2026-11-19: company_fund.utilized_fund=51968623071, accumulated_shares_purchased=18636500
--   source: 2026-10-09 Report on Shares Buyback Implementation (att 221: 36 daily trades 20 Aug - 9 Oct 2026; remaining cost Rp98,031,376,929)
update idx_buybacks set accumulated_shares_purchased = 18636500, company_fund = '[{"utilized_fund":51968623071,"allocated_fund":150000000000.0}]'::jsonb, transaction_details = '[{"date":"2026-08-20","share_amount":595900,"average_price":2548.0,"percentage_of_shares":0.06},{"date":"2026-08-21","share_amount":187900,"average_price":2552.0,"percentage_of_shares":0.02},{"date":"2026-08-24","share_amount":136200,"average_price":2482.0,"percentage_of_shares":0.01},{"date":"2026-08-26","share_amount":388200,"average_price":2474.0,"percentage_of_shares":0.04},{"date":"2026-08-27","share_amount":660100,"average_price":2553.0,"percentage_of_shares":0.07},{"date":"2026-08-28","share_amount":1331700,"average_price":2591.0,"percentage_of_shares":0.14},{"date":"2026-08-31","share_amount":305000,"average_price":2602.0,"percentage_of_shares":0.03},{"date":"2026-09-01","share_amount":270200,"average_price":2652.0,"percentage_of_shares":0.03},{"date":"2026-09-02","share_amount":168600,"average_price":2657.0,"percentage_of_shares":0.02},{"date":"2026-09-03","share_amount":196200,"average_price":2700.0,"percentage_of_shares":0.02},{"date":"2026-09-04","share_amount":781700,"average_price":2783.0,"percentage_of_shares":0.08},{"date":"2026-09-07","share_amount":2616500,"average_price":2795.0,"percentage_of_shares":0.28},{"date":"2026-09-08","share_amount":955000,"average_price":2799.0,"percentage_of_shares":0.1},{"date":"2026-09-09","share_amount":282000,"average_price":2816.0,"percentage_of_shares":0.03},{"date":"2026-09-10","share_amount":590600,"average_price":2811.0,"percentage_of_shares":0.06},{"date":"2026-09-11","share_amount":343600,"average_price":2811.0,"percentage_of_shares":0.04},{"date":"2026-09-14","share_amount":348800,"average_price":2785.0,"percentage_of_shares":0.04},{"date":"2026-09-15","share_amount":254000,"average_price":2793.0,"percentage_of_shares":0.03},{"date":"2026-09-16","share_amount":404400,"average_price":2823.0,"percentage_of_shares":0.04},{"date":"2026-09-17","share_amount":584600,"average_price":2843.0,"percentage_of_shares":0.06},{"date":"2026-09-18","share_amount":338800,"average_price":2799.0,"percentage_of_shares":0.04},{"date":"2026-09-21","share_amount":407900,"average_price":2821.0,"percentage_of_shares":0.04},{"date":"2026-09-22","share_amount":397800,"average_price":2808.0,"percentage_of_shares":0.04},{"date":"2026-09-23","share_amount":200400,"average_price":2838.0,"percentage_of_shares":0.02},{"date":"2026-09-24","share_amount":523400,"average_price":2841.0,"percentage_of_shares":0.06},{"date":"2026-09-25","share_amount":368200,"average_price":2826.0,"percentage_of_shares":0.04},{"date":"2026-09-28","share_amount":76800,"average_price":2803.0,"percentage_of_shares":0.01},{"date":"2026-09-29","share_amount":333300,"average_price":2776.0,"percentage_of_shares":0.04},{"date":"2026-09-30","share_amount":293000,"average_price":2797.0,"percentage_of_shares":0.03},{"date":"2026-10-01","share_amount":569700,"average_price":2834.0,"percentage_of_shares":0.06},{"date":"2026-10-02","share_amount":538800,"average_price":2846.0,"percentage_of_shares":0.06},{"date":"2026-10-05","share_amount":636100,"average_price":2845.0,"percentage_of_shares":null},{"date":"2026-10-06","share_amount":916000,"average_price":2946.0,"percentage_of_shares":null},{"date":"2026-10-07","share_amount":594300,"average_price":3031.0,"percentage_of_shares":null},{"date":"2026-10-08","share_amount":425800,"average_price":3035.0,"percentage_of_shares":null},{"date":"2026-10-09","share_amount":615000,"average_price":3075.0,"percentage_of_shares":null}]'::jsonb, updated_on = now()
  where symbol = 'PRDA.JK' and mandate = '{"start_date":"2026-08-20","end_date":"2026-11-19"}'::jsonb;
-- WINS 2025-06-04..2026-06-03: mandate.end_date=2026-03-31, accumulated_shares_purchased=53283500
--   source: 2026-04-01 Information Disclosure regarding Termination (att 31 Indonesian / att 32 English)
update idx_buybacks set mandate = '{"start_date":"2025-06-04","end_date":"2026-03-31"}'::jsonb, registry_updates = null, accumulated_shares_purchased = 53283500, updated_on = now()
  where symbol = 'WINS.JK' and mandate = '{"start_date":"2025-06-04","end_date":"2026-06-03"}'::jsonb;
-- ADRO 2025-06-03..2026-04-16: company_fund.allocated_fund=4000000000000, accumulated_shares_purchased=556195200
--   source: 2026-03-11 plan att 32: 556,195,200 shares bought 3 Jun 2025 - 28 Feb 2026 (latest stated; buying 1 Mar - 16 Apr 2026 unreported, so a lower bound)
update idx_buybacks set accumulated_shares_purchased = 556195200, company_fund = '[{"utilized_fund":0.0,"allocated_fund":4000000000000}]'::jsonb, updated_on = now()
  where symbol = 'ADRO.JK' and mandate = '{"start_date":"2025-06-03","end_date":"2026-04-16"}'::jsonb;
-- ERAA 2026-06-02..2026-09-02: transaction_details[date=2026-08-04].share_amount=127130900
--   source: 2026-09-02 Disclosure on the Results of Share Buyback (att p.2 totals, p.4-6 daily table, scanned)
update idx_buybacks set transaction_details = '[{"date":"2026-06-05","share_amount":8619500,"average_price":329.72,"percentage_of_shares":null},{"date":"2026-06-08","share_amount":4000000,"average_price":322.0,"percentage_of_shares":null},{"date":"2026-06-09","share_amount":300000,"average_price":330.0,"percentage_of_shares":null},{"date":"2026-06-11","share_amount":600000,"average_price":352.57,"percentage_of_shares":null},{"date":"2026-06-12","share_amount":250000,"average_price":364.0,"percentage_of_shares":null},{"date":"2026-06-22","share_amount":2000000,"average_price":368.4,"percentage_of_shares":null},{"date":"2026-06-23","share_amount":950000,"average_price":367.03,"percentage_of_shares":null},{"date":"2026-06-24","share_amount":2900000,"average_price":364.01,"percentage_of_shares":null},{"date":"2026-06-25","share_amount":1000000,"average_price":360.0,"percentage_of_shares":null},{"date":"2026-06-26","share_amount":1500000,"average_price":356.4,"percentage_of_shares":null},{"date":"2026-06-29","share_amount":2000000,"average_price":356.0,"percentage_of_shares":null},{"date":"2026-06-30","share_amount":2500000,"average_price":352.0,"percentage_of_shares":null},{"date":"2026-07-08","share_amount":3000000,"average_price":343.33,"percentage_of_shares":null},{"date":"2026-07-09","share_amount":2500000,"average_price":339.8,"percentage_of_shares":null},{"date":"2026-07-14","share_amount":3000000,"average_price":352.38,"percentage_of_shares":null},{"date":"2026-07-15","share_amount":2500000,"average_price":359.6,"percentage_of_shares":null},{"date":"2026-07-16","share_amount":2000000,"average_price":359.5,"percentage_of_shares":null},{"date":"2026-07-17","share_amount":2500000,"average_price":364.48,"percentage_of_shares":null},{"date":"2026-07-20","share_amount":2011000,"average_price":368.49,"percentage_of_shares":null},{"date":"2026-07-21","share_amount":2500000,"average_price":368.8,"percentage_of_shares":null},{"date":"2026-07-22","share_amount":10489000,"average_price":382.29,"percentage_of_shares":null},{"date":"2026-07-24","share_amount":1500000,"average_price":396.13,"percentage_of_shares":null},{"date":"2026-07-27","share_amount":2000000,"average_price":393.0,"percentage_of_shares":null},{"date":"2026-07-28","share_amount":2000000,"average_price":388.3,"percentage_of_shares":null},{"date":"2026-07-29","share_amount":3500000,"average_price":382.86,"percentage_of_shares":null},{"date":"2026-07-30","share_amount":1000000,"average_price":398.2,"percentage_of_shares":null},{"date":"2026-07-31","share_amount":2000000,"average_price":418.0,"percentage_of_shares":null},{"date":"2026-08-03","share_amount":23500000,"average_price":429.28,"percentage_of_shares":null},{"date":"2026-08-04","share_amount":127130900,"average_price":449.07,"percentage_of_shares":null},{"date":"2026-08-06","share_amount":8700000,"average_price":456.99,"percentage_of_shares":null},{"date":"2026-08-10","share_amount":1500000,"average_price":458.0,"percentage_of_shares":null},{"date":"2026-08-24","share_amount":2100000,"average_price":472.0,"percentage_of_shares":null},{"date":"2026-08-26","share_amount":4220000,"average_price":473.08,"percentage_of_shares":null}]'::jsonb, updated_on = now()
  where symbol = 'ERAA.JK' and mandate = '{"start_date":"2026-06-02","end_date":"2026-09-02"}'::jsonb;
-- JRPT 2025-10-13..2026-01-12: company_fund.allocated_fund=100000000000, company_fund.utilized_fund=21449844489, accumulated_shares_purchased=22401400, transaction_details[date=2025-01-02].date=2026-01-02
--   source: 2026-07-14 Report on Share Buyback Results until 30 Jun 2026 (att p.3 recap row 3: 22,401,400 shares, Rp21,449,844,489, remaining Rp78,550,155,511)
update idx_buybacks set accumulated_shares_purchased = 22401400, company_fund = '[{"utilized_fund":21449844489,"allocated_fund":100000000000}]'::jsonb, transaction_details = '[{"date":"2025-10-14","share_amount":484400,"average_price":859,"percentage_of_shares":0.0042},{"date":"2025-10-15","share_amount":686400,"average_price":857,"percentage_of_shares":0.0059},{"date":"2025-10-16","share_amount":330000,"average_price":860,"percentage_of_shares":0.0028},{"date":"2025-10-17","share_amount":294000,"average_price":857,"percentage_of_shares":0.0025},{"date":"2025-10-20","share_amount":464900,"average_price":862,"percentage_of_shares":0.004},{"date":"2025-10-21","share_amount":405500,"average_price":864,"percentage_of_shares":0.0036},{"date":"2025-10-22","share_amount":259300,"average_price":867,"percentage_of_shares":0.0022},{"date":"2025-10-23","share_amount":690000,"average_price":862,"percentage_of_shares":0.006},{"date":"2025-10-24","share_amount":509900,"average_price":858,"percentage_of_shares":0.0044},{"date":"2025-10-27","share_amount":178700,"average_price":860,"percentage_of_shares":0.0015},{"date":"2025-10-28","share_amount":152600,"average_price":858,"percentage_of_shares":0.0013},{"date":"2025-10-29","share_amount":460000,"average_price":859,"percentage_of_shares":0.004},{"date":"2025-10-30","share_amount":540000,"average_price":859,"percentage_of_shares":0.0046},{"date":"2025-10-31","share_amount":464200,"average_price":858,"percentage_of_shares":0.004},{"date":"2025-11-03","share_amount":590000,"average_price":859,"percentage_of_shares":0.0051},{"date":"2025-11-04","share_amount":620000,"average_price":859,"percentage_of_shares":0.0053},{"date":"2025-11-05","share_amount":640000,"average_price":858,"percentage_of_shares":0.0055},{"date":"2025-11-06","share_amount":520000,"average_price":858,"percentage_of_shares":0.0045},{"date":"2025-11-07","share_amount":799600,"average_price":862,"percentage_of_shares":0.0069},{"date":"2025-11-10","share_amount":500000,"average_price":868,"percentage_of_shares":0.0044},{"date":"2025-11-11","share_amount":195800,"average_price":872,"percentage_of_shares":0.0017},{"date":"2025-11-12","share_amount":214400,"average_price":878,"percentage_of_shares":0.0019},{"date":"2025-11-13","share_amount":341800,"average_price":878,"percentage_of_shares":0.003},{"date":"2025-11-14","share_amount":444900,"average_price":875,"percentage_of_shares":0.0039},{"date":"2025-11-17","share_amount":131300,"average_price":883,"percentage_of_shares":0.0012},{"date":"2025-11-18","share_amount":213400,"average_price":888,"percentage_of_shares":0.0019},{"date":"2025-11-19","share_amount":161900,"average_price":884,"percentage_of_shares":0.0014},{"date":"2025-11-20","share_amount":49700,"average_price":944,"percentage_of_shares":0.0005},{"date":"2025-11-21","share_amount":136800,"average_price":972,"percentage_of_shares":0.0013},{"date":"2025-11-24","share_amount":215500,"average_price":992,"percentage_of_shares":0.0021},{"date":"2025-11-25","share_amount":57900,"average_price":998,"percentage_of_shares":0.0006},{"date":"2025-11-26","share_amount":530000,"average_price":1015,"percentage_of_shares":0.0054},{"date":"2025-11-27","share_amount":640000,"average_price":1002,"percentage_of_shares":0.0064},{"date":"2025-11-28","share_amount":171200,"average_price":1008,"percentage_of_shares":0.0018},{"date":"2025-12-01","share_amount":365600,"average_price":1010,"percentage_of_shares":0.0037},{"date":"2025-12-02","share_amount":250800,"average_price":1007,"percentage_of_shares":0.0025},{"date":"2025-12-03","share_amount":152100,"average_price":1010,"percentage_of_shares":0.0015},{"date":"2025-12-04","share_amount":93500,"average_price":1012,"percentage_of_shares":0.001},{"date":"2025-12-05","share_amount":150000,"average_price":1050,"percentage_of_shares":0.0016},{"date":"2025-12-08","share_amount":910000,"average_price":1050,"percentage_of_shares":0.0095},{"date":"2025-12-09","share_amount":460000,"average_price":1066,"percentage_of_shares":0.005},{"date":"2025-12-10","share_amount":510000,"average_price":1065,"percentage_of_shares":0.0054},{"date":"2025-12-11","share_amount":276600,"average_price":1067,"percentage_of_shares":0.003},{"date":"2025-12-12","share_amount":327600,"average_price":1070,"percentage_of_shares":0.0035},{"date":"2025-12-15","share_amount":314400,"average_price":1068,"percentage_of_shares":0.0033},{"date":"2025-12-16","share_amount":205400,"average_price":1072,"percentage_of_shares":0.0023},{"date":"2025-12-17","share_amount":87400,"average_price":1072,"percentage_of_shares":0.0009},{"date":"2025-12-18","share_amount":122800,"average_price":1074,"percentage_of_shares":0.0013},{"date":"2025-12-19","share_amount":228100,"average_price":1073,"percentage_of_shares":0.0025},{"date":"2025-12-22","share_amount":340900,"average_price":1070,"percentage_of_shares":0.0036},{"date":"2025-12-23","share_amount":364000,"average_price":1071,"percentage_of_shares":0.0039},{"date":"2025-12-24","share_amount":333300,"average_price":1071,"percentage_of_shares":0.0036},{"date":"2025-12-29","share_amount":201800,"average_price":1073,"percentage_of_shares":0.0022},{"date":"2025-12-30","share_amount":135300,"average_price":1079,"percentage_of_shares":0.0014},{"date":"2026-01-02","share_amount":82800,"average_price":1084,"percentage_of_shares":0.0009},{"date":"2026-01-05","share_amount":189700,"average_price":1077,"percentage_of_shares":0.0021},{"date":"2026-01-06","share_amount":100000,"average_price":1080,"percentage_of_shares":0.0011},{"date":"2026-01-07","share_amount":559500,"average_price":1075,"percentage_of_shares":0.006},{"date":"2026-01-08","share_amount":1113800,"average_price":1060,"percentage_of_shares":0.0118},{"date":"2026-01-09","share_amount":1200000,"average_price":1049,"percentage_of_shares":0.0127},{"date":"2026-01-12","share_amount":231900,"average_price":1050,"percentage_of_shares":0.0024}]'::jsonb, updated_on = now()
  where symbol = 'JRPT.JK' and mandate = '{"start_date":"2025-10-13","end_date":"2026-01-12"}'::jsonb;
-- JRPT 2026-06-04..2027-06-04: company_fund.utilized_fund=4171774335
--   source: 2026-07-14 Report until 30 Jun 2026 (att p.3: 4 Jun-26 Jun 2026 'Buyback RUPS' 3,868,800 shares, Rp4,171,774,335)
update idx_buybacks set company_fund = '[{"utilized_fund":4171774335,"allocated_fund":100000000000.0}]'::jsonb, updated_on = now()
  where symbol = 'JRPT.JK' and mandate = '{"start_date":"2026-06-04","end_date":"2027-06-04"}'::jsonb;
-- JATI 2026-03-09..2026-06-08: company_fund.utilized_fund=9000466382, accumulated_shares_purchased=86540200
--   source: 2026-06-25 'Buyback or Payment of Bond(s) and Sukuk(s)' (att 02 p.1-2: previous program ended 8 Jun 2026 with 86,540,200 shares (53.05% of max), total funds used Rp9,000,466,382 incl. all costs)
update idx_buybacks set accumulated_shares_purchased = 86540200, company_fund = '[{"utilized_fund":9000466382,"allocated_fund":35000000000.0}]'::jsonb, updated_on = now()
  where symbol = 'JATI.JK' and mandate = '{"start_date":"2026-03-09","end_date":"2026-06-08"}'::jsonb;
-- KREN 2025-06-16..2026-06-16: company_fund.allocated_fund=50000000000
--   source: 2026-06-25 Share Buyback Report period 16 Jun 2025 - 16 Jun 2026 (att PDF p.1-2: 15 Jun 2026, 3,500,000 shares @ avg Rp14)
update idx_buybacks set company_fund = '[{"utilized_fund":0.0,"allocated_fund":50000000000}]'::jsonb, updated_on = now()
  where symbol = 'KREN.JK' and mandate = '{"start_date":"2025-06-16","end_date":"2026-06-16"}'::jsonb;
-- GOTO 2025-06-19..2026-06-18: company_fund.allocated_fund=3300000000000
--   source: 2026-06-18 Report regarding End of Period of 2025-2026 Share Buyback (main + att 81: period 19 Jun 2025 - 18 Jun 2026 approved by EGMS 18 Jun 2025, 7,593,660,600 Series A shares; treasury 39,780,078,403)
update idx_buybacks set company_fund = '[{"utilized_fund":0.0,"allocated_fund":3300000000000}]'::jsonb, updated_on = now()
  where symbol = 'GOTO.JK' and mandate = '{"start_date":"2025-06-19","end_date":"2026-06-18"}'::jsonb;
-- TBIG 2026-01-30..2026-04-29: mandate.start_date=2025-10-30, company_fund.allocated_fund=360000000000
--   source: 2026-01-29 Plan for the first extension of the share buyback period (att 11 p.1-3, scanned: extension 30 Jan - 29 Apr 2026; 56,978,600 shares bought until 29 Jan 2026)
update idx_buybacks set mandate = '{"start_date":"2025-10-30","end_date":"2026-04-29"}'::jsonb, registry_updates = null, company_fund = '[{"utilized_fund":0.0,"allocated_fund":360000000000}]'::jsonb, updated_on = now()
  where symbol = 'TBIG.JK' and mandate = '{"start_date":"2026-01-30","end_date":"2026-04-29"}'::jsonb;
-- DEWA 2025-11-18..2026-02-13: mandate.start_date=2025-11-19
--   source: 2025-11-18 plan att 02: buyback period 19 Nov 2025 - 19 Feb 2026
update idx_buybacks set mandate = '{"start_date":"2025-11-19","end_date":"2026-02-13"}'::jsonb, registry_updates = null, updated_on = now()
  where symbol = 'DEWA.JK' and mandate = '{"start_date":"2025-11-18","end_date":"2026-02-13"}'::jsonb;
-- AMOR 2025-05-22..2026-01-28: company_fund.allocated_fund=4500000000
--   source: 2026-01-28 Share Buyback Termination (att sec. B: ended early 28 Jan 2026, 10.616.800 shares, Rp4,499,325,509 incl. fees)
update idx_buybacks set company_fund = '[{"utilized_fund":4499325509.0,"allocated_fund":4500000000}]'::jsonb, updated_on = now()
  where symbol = 'AMOR.JK' and mandate = '{"start_date":"2025-05-22","end_date":"2026-01-28"}'::jsonb;
-- ASLC 2026-05-20..2026-06-30: mandate.end_date=2027-05-19
--   source: 2026-04-10 plan att 32: period 12 months from 20 May 2026
update idx_buybacks set mandate = '{"start_date":"2026-05-20","end_date":"2027-05-19"}'::jsonb, registry_updates = null, updated_on = now()
  where symbol = 'ASLC.JK' and mandate = '{"start_date":"2026-05-20","end_date":"2026-06-30"}'::jsonb;
-- BBNI 2026-03-09..2027-03-08: mandate.end_date=2026-07-06
--   source: 2026-07-06 Termination and Completion of the 2026 Share Buyback (att p.2: AGMS 9 Mar 2026; terminated, 77.856.100 shares)
update idx_buybacks set mandate = '{"start_date":"2026-03-09","end_date":"2026-07-06"}'::jsonb, registry_updates = null, updated_on = now()
  where symbol = 'BBNI.JK' and mandate = '{"start_date":"2026-03-09","end_date":"2027-03-08"}'::jsonb;

-- 2. Rows that are not buyback programs, or duplicates
-- PLAS: 2026-09-23 Disclosure regarding the Procedures for the Repurchase of Shares in Connection with the Delisting of Shares: mandatory repurchase at Rp51/share (Rp60
delete from idx_buybacks where symbol = 'PLAS.JK' and mandate = '{"start_date":"2026-09-24","end_date":"2026-11-06"}'::jsonb;
-- SMAR: 2026-05-22 plan and 2026-06-05 report: repurchase offered under Article 62(1) Company Law to shareholders who voted against the merger of PT Perusahaan Perkebun
delete from idx_buybacks where symbol = 'SMAR.JK' and mandate = '{"start_date":"2026-05-25","end_date":"2026-06-03"}'::jsonb;
-- MORA: Repurchase for shareholders dissenting from the MORA-EMR merger under Art. 62 Company Law (2026-03-27 disclosure; cap Rp1,021,536,087,408 at Rp432). 2026-04-22 
delete from idx_buybacks where symbol = 'MORA.JK' and mandate = '{"start_date":"2026-04-01","end_date":"2026-04-17"}'::jsonb;
-- MTEL: Repurchase of 69,777,200 shares (Rp35,935,258,000 at Rp515) from shareholders dissenting from the merger with PT Persada Sokka Tama / PT Ultra Mandiri Telekomun
delete from idx_buybacks where symbol = 'MTEL.JK' and mandate = '{"start_date":"2026-07-03","end_date":"2026-07-10"}'::jsonb;
-- UNTR: No filing describes a program on 12 Feb 2026. Row duplicates the Oct 2025 - 14 Jan 2026 program's figures (allocated 2tn, utilized 1,999,990,270,702, accumulate
delete from idx_buybacks where symbol = 'UNTR.JK' and mandate = '{"start_date":"2026-02-12","end_date":"2026-02-12"}'::jsonb;

-- 3. Missing programs with filing-confirmed dates and budget
-- ALDO 2025-06-12..2026-06-11 (gms): 2026-06-02 ALDO Share Buyback Plan (att p.1: previous program ends 11 Jun 2026)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('ALDO.JK', '{"start_date":"2025-06-12","end_date":"2026-06-11"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":10000000000.0}]'::jsonb, 0, now()) on conflict do nothing;
-- JTPE 2025-12-15..2026-03-06 (fluctuating): 2025-12-09 Plan for Share Buyback under Significant Market Fluctuation (att 01: period 15 Dec 2025 - 06 Mar 2026; max Rp140,000,000,000 incl. costs; max 342,602,500 shares; m
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('JTPE.JK', '{"start_date":"2025-12-15","end_date":"2026-03-06"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":140000000000.0}]'::jsonb, 0, now()) on conflict do nothing;
-- GEMA 2025-12-12..2026-03-12 (fluctuating): 2025-12-15 REPURCHASE RESULTS REPORT (att 11 p.2: 15 Dec 2025, 1,000,000 shares @ Rp94.5, remaining cost Rp6,905,500,000)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('GEMA.JK', '{"start_date":"2025-12-12","end_date":"2026-03-12"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":7000000000.0}]'::jsonb, 1000000, now()) on conflict do nothing;
-- ISSP 2026-05-25..2026-08-25 (fluctuating): 2026-07-14 Share Buyback Realization Report (att 31 cover letter; att 32 table 25 May - 30 Jun 2026, Jumlah 12,980,200)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('ISSP.JK', '{"start_date":"2026-05-25","end_date":"2026-08-25"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":200000000000.0}]'::jsonb, 12980200, now()) on conflict do nothing;
-- MAHA 2025-10-23..2026-03-16 (fluctuating): 2025-10-23 The Company's Share Buyback Plan during Significantly Fluctuating Market Conditions (att 01 sections 1, 2, 7)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('MAHA.JK', '{"start_date":"2025-10-23","end_date":"2026-03-16"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":153681785824.0}]'::jsonb, 0, now()) on conflict do nothing;
-- BBCA 2025-10-22..2026-01-19 (fluctuating): 2025-10-20 Shares Buyback Plan in Significantly Fluctuating Market Conditions (att: period 22 Oct 2025-19 Jan 2026, Rp5tn, max price Rp9,200)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('BBCA.JK', '{"start_date":"2025-10-22","end_date":"2026-01-19"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":5000000000000.0}]'::jsonb, 0, now()) on conflict do nothing;
-- HRUM 2025-10-06..2026-01-02 (fluctuating): 2025-10-03 Disclosure on Plan to Implement Shares Buyback in Fluctuating Market (att p.3-4, scanned)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('HRUM.JK', '{"start_date":"2025-10-06","end_date":"2026-01-02"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":837000000000.0}]'::jsonb, 0, now()) on conflict do nothing;
-- AGRO 2025-06-25..2026-06-25 (gms): 2026-07-15 Report on Realization up to 30 June 2026 (att p.1-2: period ended 25 Jun 2026; 10,818,300 shares, nominal Rp2,055,462,687 + costs Rp660,496,223; remaining budget Rp17,284,
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('AGRO.JK', '{"start_date":"2025-06-25","end_date":"2026-06-25"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":2715958910.0,"allocated_fund":20000000000.0}]'::jsonb, 10818300, now()) on conflict do nothing;
-- CNMA 2025-03-24..2026-02-20 (gms): 2026-02-20 Disclosure on Termination of the Share Buyback Period (att 32: AGMS 24 Mar 2025, period until 24 Mar 2026, terminated early per BoD circular resolution 18 Feb 2026; 1,698,
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('CNMA.JK', '{"start_date":"2025-03-24","end_date":"2026-02-20"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":300000000000.0}]'::jsonb, 1698015400, now()) on conflict do nothing;
-- JATI 2026-06-26..2026-09-25 (fluctuating): 2026-06-25 'Buyback or Payment of Bond(s) and Sukuk(s)' (main + att 02: Buyback Tahap II, up to Rp25,999,533,617 from internal cash; period 26 Jun - 25 Sep 2026; POJK 13/2023
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('JATI.JK', '{"start_date":"2026-06-26","end_date":"2026-09-25"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":25999533617.0}]'::jsonb, 0, now()) on conflict do nothing;
-- MYOR 2025-06-11..2026-05-29 (gms): 2026-05-20 Changes to the Schedule for the Implementation of Share Buybacks (att p.1, scanned: EGMS 10 Jun 2025; period originally 11 Jun 2025 - 11 Jun 2026, changed to 11 Jun 2025 -
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('MYOR.JK', '{"start_date":"2025-06-11","end_date":"2026-05-29"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":1000000000000.0}]'::jsonb, 0, now()) on conflict do nothing;
-- BUKA 2025-10-30..2026-01-29 (fluctuating): 2026-02-06 Disclosure of Information on Share Buyback Plan (att 2026-02-06_63 p.1: Phase III ran 30 Oct 2025 - 29 Jan 2026, remaining unused fund IDR 280,993,812,026)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('BUKA.JK', '{"start_date":"2025-10-30","end_date":"2026-01-29"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":420794871507.0}]'::jsonb, 0, now()) on conflict do nothing;
-- ASII 2025-11-03..2026-01-13 (fluctuating): 2026-01-14 Termination of The Implementation of Share Buyback (att 11 p.2-3, scanned: ended 13 Jan 2026, 305,213,900 shares, Rp1,999,999,829,789)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('ASII.JK', '{"start_date":"2025-11-03","end_date":"2026-01-13"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":1999999829789.0,"allocated_fund":2000000000000.0}]'::jsonb, 305213900, now()) on conflict do nothing;
-- AVIA 2025-04-10..2026-04-10 (gms): 2025-04-17 Appointment of Exchange Member (att 10 p.1: refers to EGMS resolution dated 10 Apr 2025, appoints Verdhana Sekuritas)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('AVIA.JK', '{"start_date":"2025-04-10","end_date":"2026-04-10"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":1000000000000.0}]'::jsonb, 0, now()) on conflict do nothing;
-- TOBA 2025-12-24..2026-03-24 (fluctuating): 2025-12-25 Shares Buyback Plan in Significantly Fluctuating Market Conditions (att 01: period 24 Desember 2025 - 24 Maret 2026, max Rp586.275.608.030 (US$34,918,142), max 825
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('TOBA.JK', '{"start_date":"2025-12-24","end_date":"2026-03-24"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":586275608030.0}]'::jsonb, 0, now()) on conflict do nothing;
-- AADI 2025-05-23..2026-05-22 (gms): 2026-04-21 Additional Information on The Plan for Share Buyback (att 21 sec. II: approved at RUPST 22 Mei 2025, period 23 Mei 2025 - 22 Mei 2026; no repurchases executed 23 Mei 2025 
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('AADI.JK', '{"start_date":"2025-05-23","end_date":"2026-05-22"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":4000000000000.0}]'::jsonb, 0, now()) on conflict do nothing;
-- BBHI 2025-10-30..2026-01-29 (fluctuating): 2026-01-29 Share buyback plan (att 31/32: buyback 30 Okt 2025 - 29 Jan 2026 completed; remaining funds Rp60,651,512,454)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('BBHI.JK', '{"start_date":"2025-10-30","end_date":"2026-01-29"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":119375389981.0}]'::jsonb, 0, now()) on conflict do nothing;
-- NCKL 2025-06-19..2026-06-18 (gms): 2026-05-22 The Proposed Share Buyback (att 01 p.2: 2025 Share Buyback approved by AGMS 18 Jun 2025, max Rp1,000,000,000,000, period 19 Jun 2025 - 18 Jun 2026)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('NCKL.JK', '{"start_date":"2025-06-19","end_date":"2026-06-18"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":1000000000000.0}]'::jsonb, 0, now()) on conflict do nothing;
-- AMAG 2025-10-23..2026-01-23 (fluctuating): 2025-10-23 The Company shares buyback in Significant Market Fluctuation (att p.1-2: schedule 23 Okt 2025 s/d 23 Jan 2026, max Rp90.150.000.000, max 237.194.064 shares)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('AMAG.JK', '{"start_date":"2025-10-23","end_date":"2026-01-23"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":90150000000.0}]'::jsonb, 0, now()) on conflict do nothing;
-- AMAG 2026-01-26..2026-04-26 (fluctuating): 2026-01-23 Share Buybacks in Significantly Fluctuating Market Conditions (att p.1-2: 26 Jan 2026 s/d 26 Apr 2026, max Rp90.150.000.000, max 237.194.064 shares, max price Rp42
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('AMAG.JK', '{"start_date":"2026-01-26","end_date":"2026-04-26"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":90150000000.0}]'::jsonb, 0, now()) on conflict do nothing;
-- ASLC 2025-06-18..2026-05-12 (gms): 2026-05-13 Share Buyback Realization Report (no purchases 1 Jan-12 May 2026)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('ASLC.JK', '{"start_date":"2025-06-18","end_date":"2026-05-12"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":50000000000.0}]'::jsonb, 0, now()) on conflict do nothing;
-- BBNI 2025-03-26..2026-02-20 (gms): 2026-02-20 Report on Completion of the Share Buyback (att p.2: AGMS 26 Mar 2025 approved Rp1.5T; completed with 16.377.700 shares)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('BBNI.JK', '{"start_date":"2025-03-26","end_date":"2026-02-20"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":1500000000000.0}]'::jsonb, 16377700, now()) on conflict do nothing;
-- BBNI 2026-07-27..2026-10-26 (fluctuating): 2026-07-27 Information Disclosure re Proposed Share Buyback under Significantly Fluctuating Market Conditions (att: 27 Jul-26 Oct 2026, max Rp627.000.000.000 (enam ratus dua 
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('BBNI.JK', '{"start_date":"2026-07-27","end_date":"2026-10-26"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":627000000000.0}]'::jsonb, 0, now()) on conflict do nothing;
-- BEEF 2026-05-19..2026-08-18 (fluctuating): 2026-08-19 Result of the implementation Buy Back 19 May-18 Aug 2026 (att: total 52.558.600 shares, Rp9,456,904,535)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('BEEF.JK', '{"start_date":"2026-05-19","end_date":"2026-08-18"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":9456904535.0,"allocated_fund":100000000000.0}]'::jsonb, 52558600, now()) on conflict do nothing;
-- CHEK 2026-06-18..2026-09-18 (fluctuating): 2026-09-18 Report on Realization and Completion of the 2026 Share Buyback (att p.2: 80.000.000 shares, 1,94%, Rp11.987.865.437 funds used, avg Rp140,95; att p.5 trade table)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('CHEK.JK', '{"start_date":"2026-06-18","end_date":"2026-09-18"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":11987865437.0,"allocated_fund":15000000000.0}]'::jsonb, 80000000, now()) on conflict do nothing;
-- KLBF 2025-12-16..2026-03-15 (fluctuating): 2025-12-12 Share Buyback Plan in Significantly Fluctuating Market Conditions (att 21: period 16 Dec 2025 - 15 Mar 2026, max Rp250.000.000.000)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('KLBF.JK', '{"start_date":"2025-12-16","end_date":"2026-03-15"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":250000000000.0}]'::jsonb, 0, now()) on conflict do nothing;
-- MEDC 2025-06-04..2026-06-03 (gms): 2026-04-28 Disclosure on transfer of shares (att 62 p.4-5: treasury 455,609,908 as of 31 Mar 2026 = 2024 buyback + Phase I + Phase II only)
insert into idx_buybacks (symbol, mandate, transaction_details, company_fund, accumulated_shares_purchased, updated_on)
  values ('MEDC.JK', '{"start_date":"2025-06-04","end_date":"2026-06-03"}'::jsonb, '[]'::jsonb, '[{"utilized_fund":0.0,"allocated_fund":408000000000.0}]'::jsonb, 0, now()) on conflict do nothing;

commit;

-- Not written (needs a filing that confirms it):
--   BBRI 2025-03-25..2026-03-24: GMS approval not confirmed by a post-meeting filing
--   BNGA 2025-04-14..2026-04-14: GMS approval not confirmed by a post-meeting filing
--   BNGA 2026-04-17..2027-04-16: GMS approval not confirmed by a post-meeting filing
--   BTPS 2026-10-14..2027-10-13: GMS approval not confirmed by a post-meeting filing
--   GOOD 2025-04-24..None: Plan: up to Rp50bn incl. fees, ~0.35% = 130,562,827 shares, period up to 12 months after EGMS approval; EGMS scheduled 2
--   GOOD None..None: dates not known yet
--   ADRO 2026-04-18..2027-04-17: GMS approval not confirmed by a post-meeting filing
--   BBCA 2026-03-12..2027-03-12: GMS approval not confirmed by a post-meeting filing
--   EPAC None..None: dates not known yet
--   MTEL 2025-09-16..2026-09-15: POJK 29 plan for Rp1tn, 12 months from EGMS of 16 Sep 2025 (would overlap 2026). No local filing confirms EGMS approval,
--   STAA 2025-06-12..2026-06-11: GMS approval not confirmed by a post-meeting filing
--   TLKM 2025-05-28..2026-05-27: GMS approval not confirmed by a post-meeting filing
--   TLKM 2026-06-09..2027-06-08: GMS approval not confirmed by a post-meeting filing
--   DOID None..2027-06-24: dates not known yet
--   LPPF 2025-04-10..2026-04-10: GMS approval not confirmed by a post-meeting filing
--   MPMX None..None: dates not known yet
--   BMRI 2025-03-26..2026-03-25: GMS approval not confirmed by a post-meeting filing
--   ITMG 2025-11-04..2026-11-04: GMS approval not confirmed by a post-meeting filing
--   KEJU 2025-04-23..2026-04-22: GMS approval not confirmed by a post-meeting filing
--   KEJU 2026-04-22..2027-04-21: GMS approval not confirmed by a post-meeting filing
--   AADI 2026-05-23..2027-05-22: GMS approval not confirmed by a post-meeting filing
--   ASMI 2025-05-27..2026-05-27: The 2025 plan's RUPSLB was 2025-05-27. The approval minutes are not in the local files. The 2026 filings refer to a 'pre
--   ASMI None..None: dates not known yet
--   CBDK 2026-05-20..2026-08-19: Dates, allocation and utilized_fund 61,569,478,344 match. The filing contradicts itself on shares: the detailed table to
--   NISP 2025-03-20..2026-03-19: GMS approval not confirmed by a post-meeting filing
--   NISP 2026-04-09..2027-04-08: GMS approval not confirmed by a post-meeting filing
--   SMIL None..None: A POJK 29/2023 (GMS) plan announced 25 Aug 2025; if approved at a GMS in late 2025 its 12-month period would overlap 202
--   BBMD 2025-06-20..2026-06-20: GMS approval not confirmed by a post-meeting filing
--   SMGR 2025-05-24..2026-05-23: Plan overlaps 2026 but no local filing confirms GMS approval on 23 May 2025 or any execution/progress report. Add as mis
