+++
author = "Meswsoul"
title = "分享APScheduler的工作案例，以及子線程可能導致的異常"
date = "2025-01-25"
description = "實作Apscheduler與兩種子線程管理"
tags = [

    "Python",

]
categories = [

    "Tech-Notes",

]
series = ["Python"]
image = "default-cover.png"
+++

> AI越來越普及，人手一個Python自動化，
> 當你需要定期執行任務，例如資料備份、或抓取 API 資料，對於這類需求，
> 推薦使用Python 強大的排程框架：
> [APScheduler](https://apscheduler.readthedocs.io/en/3.x/)。

## 實際案例: 客戶端的倒計時程式

工作上，有一個在客戶端運行的Python App，它輪詢訪問我司後端，獲取最新任務設置，將其保存在本地，
之後，靠APScheduler去定期執行offline任務，當任務完成，將成果打包並上傳回我們後端。
可以將它想成是一個遠程的搬運工。

這樣的設計，優點是後端清爽簡單，處理時序的邏輯都集中在客戶端，
缺點是，一但出現問題，只能依賴客戶提供的offline log去debug，無法取得詳細資料。

## 異常

最近遇到一個弔詭的問題：App  突然停止訪問後端、也停止上傳成果檔案。
Log顯示，依然穩定地執行離線任務，並且持續打包結果，看似調度器（Scheduler）也是正常的。
這問題在好幾個客戶端都出現過。一但遇到，只有將App重啟才會恢復正常。

最初猜想是與後端之間連接的問題導致，但看完issue log矇了，
主程序本來應該不斷的嘗試，但它偶爾會在一次正常的連線後，就再也沒有嘗試與後端連接（就像約會後神隱了一樣？）。

## 到底什麼出錯了？

* **當系統崩潰、且主進程未正確管理子進程時，子進程會殘留，導致不可預期的行為**

基本上，主程序崩潰，子作業會中止。
當你執行一個 Python 腳本時，Python 解釋器會啟動一個主進程（main process）來運行代碼，所有的線程都是由主進程創建和管理的。

而APScheduler的調度器也是由主進程管理的。當主程序崩潰，調度器停止運行，所有子作業也應該被強制中止才對，
只是剛好我的case，子任務時間持續Ｎ個小時，以致於主程序崩潰後，還不斷地產生新的log。

> 註：如果使用多進程（multiprocessing 模塊），則主進程會生成子進程來執行工作。
> 每個子進程都有獨立的記憶體空間和 Python 解釋器，不受 GIL 的限制。但最好還是設置，讓主進程管理這些子進程，後面會提到。

## 實驗

模擬一個小任務，並試著在子進程/線程尚未結束時之前退出主程序，這樣就能重現錯誤囉 (reproduce)。

```python
def run(logger):
    """simulate a task"""
    logger.info('running from Func')
    time.sleep(5)
    logger.info('end of running from Func')
```

### 實驗1 - ThreadPoolExecutor

對於 I/O 密集型任務，用 `ThreadPoolExecutor` (也是默認的執行器)

```python
    logger = create_logger()
    
    scheduler = BackgroundScheduler(
         executors={'default': ThreadPoolExecutor(1)}
    )

    scheduler.start()
    scheduler.add_job(run, 'interval', args=[logger], seconds=5, max_instances=5)

    try:
        logger.info("Scheduler is running. Press Ctrl+C to exit.")
        while True:
            for i in range(20):
                logger.info(f'main running {i} sec')
                time.sleep(1)
            exit(88)
    except (KeyboardInterrupt, SystemExit) as e:
        logger.error(f"Main program terminated {e}")
        scheduler.shutdown(wait=False)

```

可以看到，子進程在主程序報錯Exit code後，繼續寫下log才退出。

```
2025-01-15 15:52:57,207 - MyAppLogger - INFO - Scheduler is running. Press Ctrl+C to exit.
2025-01-15 15:52:57,207 - MyAppLogger - INFO - main running 0 sec
2025-01-15 15:52:58,208 - MyAppLogger - INFO - main running 1 sec
2025-01-15 15:52:59,210 - MyAppLogger - INFO - main running 2 sec
2025-01-15 15:53:00,211 - MyAppLogger - INFO - main running 3 sec
2025-01-15 15:53:01,212 - MyAppLogger - INFO - main running 4 sec
2025-01-15 15:53:02,207 - MyAppLogger - INFO - running from Func
2025-01-15 15:53:02,213 - MyAppLogger - INFO - main running 5 sec
2025-01-15 15:53:03,215 - MyAppLogger - INFO - main running 6 sec
2025-01-15 15:53:04,215 - MyAppLogger - INFO - main running 7 sec
2025-01-15 15:53:05,216 - MyAppLogger - INFO - main running 8 sec
2025-01-15 15:53:06,217 - MyAppLogger - INFO - main running 9 sec
2025-01-15 15:53:07,213 - MyAppLogger - INFO - end of running from Func
2025-01-15 15:53:07,213 - MyAppLogger - INFO - running from Func
2025-01-15 15:53:07,218 - MyAppLogger - INFO - main running 10 sec
...
2025-01-15 15:53:16,231 - MyAppLogger - INFO - main running 19 sec
2025-01-15 15:53:17,225 - MyAppLogger - INFO - end of running from Func
2025-01-15 15:53:17,225 - MyAppLogger - INFO - running from Func
2025-01-15 15:53:17,233 - MyAppLogger - ERROR - Main program terminated 88
2025-01-15 15:53:22,226 - MyAppLogger - INFO - end of running from Func

```

### 實驗2 - ProcessPoolExecutor

替換成以下，結果一樣等待子進程執行完才結束:

```python
    # 預設為False，非守護進程（non-daemon）
    # multiprocessing.current_process().daemon = True
    scheduler = BackgroundScheduler(
        executors={'default': ProcessPoolExecutor(1)}
    )
--
2025-01-15 15:56:43, 915 - MyAppLogger - INFO - main running 19 sec
2025-01-15 15:56:44, 917 - MyAppLogger - ERROR - Main program terminated 88
>>> Still waiting on run() for 5 seconds
# 因為進程隔離，logger不共享，stdout沒有被正確pipe到主程序，
# 需要在在run中重新配置logger才能打印出來，這裡就沒有多做
```

若將修改當前進程的 daemon 屬性為True，將其設置為護進程（daemon process），
代表當前進程會在父進程終止時自動結束，而不會阻塞或繼續執行，會得到錯誤
`AssertionError: daemonic processes are not allowed to have children` ，當然，這也不是我們想要的結果就是了。

## 結語，除了handle好錯誤，還有那些補救方案?

我解決掉會讓主程序崩潰的一個小bug，App不崩潰，那這次問題也就排除了。

只是難免又有漏洞，還有什麼好辦法呢？
以下整理常見的補救主程序崩潰的做法：
1. 設定cron job 或使用systemd監控 (Linux)，一旦崩潰，重啟主程序。
1. 使用 Celery 或 Redis Queue (RQ)，讓作業完全脫離主程序的調度。
APScheduler 僅負責排程，執行交給獨立的作業管理器或worker。
它額外的好處是支援**持久化**，主程序重啟後，未完成的作業可以繼續執行。

## 參考

* 使用Event管理子進程, [Python Multiprocessing graceful shutdown in the proper order](https://www.peterspython.com/en/blog/python-multiprocessing-graceful-shutdown-in-the-proper-order)
* [Python 定时任务框架 APScheduler 详解](https://www.cnblogs.com/leffss/p/11912364.html)
