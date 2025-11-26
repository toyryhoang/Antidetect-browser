const TOO_MUCH_COOKIES = 1000

let BASE_URL
let UID
let isCookieChangeListenerOn = false
let debounceSavingCookies = debounce(storeCookies, 5000)

chrome.contextMenus.create({
  id: 'humanTyping',
  title: 'Paste like typing (Ctrl+Shift+F)',
  contexts: ['editable'],
  onclick: onClickHumanTyping,
})

chrome.commands.onCommand.addListener((command) => {
  if (command == 'humanTyping') {
    onClickHumanTyping()
  }
})

chrome.cookies.onChanged.addListener(() => {
  if (isCookieChangeListenerOn) {
    debounceSavingCookies()
  }
})

chrome.windows.onRemoved.addListener(() => {
  storeCookies()
})

// Подсчет вкладок, т.к. при закрытии браузера на Mac он сворачивается
// Если вкладок 0 (вкладки обнуляются при закрытии) шлём сигнал на принудительное завершение
chrome.tabs.onRemoved.addListener((tab) => {
  chrome.tabs.query({}, (tabs) => {
    if (tabs.length === 0) {
      storeCookies(() => {
        fetch(`${BASE_URL}/close/${UID}`)
      })
    }
  })
})

function onClickHumanTyping(info, tab) {
  chrome.tabs.executeScript({
    file: 'content/human-typing.js',
  })
}

function logError(msg) {
  console.error(msg)
}

function logInfo(msg) {
  console.log(msg)
}

function debounce(func, timeMs) {
  let timeout
  return function () {
    clearTimeout(timeout)
    timeout = setTimeout(() => func(), timeMs)
  }
}

function buildCookieURL(domain, secure, path) {
  const domainWithoutDot = domain && domain.startsWith('.') ? domain.substr(1) : domain
  return 'http' + (secure ? 's' : '') + '://' + domainWithoutDot + path
}

function isHostOrSecure(cookieName) {
  return cookieName.startsWith('__Host-') || cookieName.startsWith('__Secure-')
}

function processSecureAndHost(cookie) {
  cookie.url = cookie.url.replace('http:', 'https:')
  cookie.secure = true
  if (cookie.name.startsWith('__Host-')) {
    delete cookie.domain
  }
}

function shouldSkipCookie(cookie) {
  const skipStrategies = [
    // возникает ошибка битых кук на gmail, если выставлять данные куки
    /(http|https):\/\/mail.google.com\//.test(cookie.url) && ['OSID', '__Secure-OSID'].includes(cookie.name),
    /(http|https):\/\/ads.google.com\//.test(cookie.url) && ['OSID'].includes(cookie.name),
    // то же самое outlook
    /(http|https):\/\/outlook.live.com/.test(cookie.url) && ['DefaultAnchorMailbox'].includes(cookie.name),
  ]

  return skipStrategies.some((strategy) => strategy)
}

function cleanCookieProperties(cookie) {
  delete cookie.browserType
  delete cookie.storeId

  if (cookie.session) {
    delete cookie.expirationDate
  }
  delete cookie.session

  // make host-only
  if (cookie.hostOnly && cookie.domain && !cookie.domain.startsWith('.')) {
    delete cookie.domain
  }
  delete cookie.hostOnly
}

function isValidDate(date) {
  return date instanceof Date && date.toString() !== 'Invalid Date'
}

function addDays(date, days) {
  const _date = new Date(Number(date))
  _date.setDate(date.getDate() + days)
  return _date
}

function updateExpirationDate(cookie) {
  if (cookie.expirationDate) {
    if (/(http|https):\/\/mail.google.com\//.test(cookie.url) && cookie.name === 'COMPASS') {
      delete cookie.expirationDate
      return
    }

    const today = new Date()
    const _expirationDate = new Date(cookie.expirationDate * 1000)
    if (isValidDate(_expirationDate) && _expirationDate < today) {
      const plusThreeDays = addDays(today, 3)
      cookie.expirationDate = plusThreeDays.getTime() / 1000
      return
    }
  }
}

function setCookie(cookie) {
  return new Promise((resolve, reject) => {
    chrome.cookies.set(cookie, () => {
      if (chrome.runtime.lastError) {
        logError('Cannot set cookie.' + chrome.runtime.lastError.message)
        resolve({ status: 'error', data: cookie, message: chrome.runtime.lastError.message })
      } else {
        resolve({ status: 'success', data: cookie })
      }
    })
  })
}

function setCookies(data) {
  if (data && Array.isArray(data)) {
    logInfo('Set cookies...')

    const cookiePromises = []
    const skipCookies = []

    for (let cookie of data) {
      // for imported cookies
      if (!cookie.url) {
        cookie.url = buildCookieURL(cookie.domain, cookie.secure, cookie.path)
      }

      cleanCookieProperties(cookie)
      updateExpirationDate(cookie)

      if (isHostOrSecure(cookie.name)) {
        processSecureAndHost(cookie)
      }

      if (!shouldSkipCookie(cookie)) {
        cookiePromises.push(setCookie(cookie))
      } else {
        skipCookies.push(cookie)
      }
    }

    console.log('Skip cookies', skipCookies)

    return Promise.all(cookiePromises)
  }

  return Promise.resolve([])
}

function sessionReady() {
  fetch(`${BASE_URL}/session/ready`)
    .then(() => logInfo('Everything is ready'))
    .catch((error) => logError(error.message))
}

function storeCookies(successCallback) {
  successCallback && successCallback()
  return true

  chrome.cookies.getAll({}, (cookies) => {
    let cookiesBody = cookies.map(
      ({ domain, name, value, hostOnly, path, secure, httpOnly, sameSite, session, expirationDate = 0 }) => {
        const url = buildCookieURL(domain, secure, path)
        return { url, domain, name, value, hostOnly, path, secure, httpOnly, sameSite, session, expirationDate }
      }
    )

    logInfo('Saving cookies...')

    fetch(`${BASE_URL}/cookies/${UID}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(cookiesBody),
    })
      .then(() => successCallback && successCallback())
      .catch((error) => {
        const message = 'Failed to save data. Please try again later'
        logError(`${message}: ${error.message}`)
      })
  })
}

function bptimer() {
  return fetch(`${BASE_URL}/timer/update/${UID}`)
}

function start(data) {
  setInterval(bptimer, 5000)
  sessionReady()

  console.log('Cookies count from API', data.length)

  chrome.cookies.remove({
    url: 'https://myip.gologin.app',
    name: 'gologin.cookie',
  })

  chrome.cookies.getAll({}, (cookies) => {
    const cookiesStats = {
      dbCookiesCount: data.length,
      chromeApiCount: cookies.length,
      cookiesDifferenceValues: [],
      uniqueDbCookies: [],
    }

    // todo: сравнивать домены после удаления начальных точек (не важно есть или нет)
    if (data.length !== cookies.length) {
      cookiesStats.uniqueDbCookies = data.filter(
        (dbCookie) =>
          cookies.findIndex(
            ({ domain, name, path }) => dbCookie.domain === domain && dbCookie.name === name && dbCookie.path === path
          ) === -1
      )
    }

    data.forEach((dbCookie) => {
      const sameCookie = cookies.find(
        ({ domain, name, path }) => dbCookie.domain === domain && dbCookie.name === name && dbCookie.path === path
      )

      if (sameCookie && sameCookie.value !== dbCookie.value)
        cookiesStats.cookiesDifferenceValues.push({ db: dbCookie, chrome: sameCookie })
    })

    const diffCoookies = [...cookiesStats.uniqueDbCookies, ...cookiesStats.cookiesDifferenceValues.map(({ db }) => db)]

    setCookies(diffCoookies).then((data) => {
      isCookieChangeListenerOn = true

      console.log('data', data)
      console.log(
        'error cookies',
        data.filter(({ status }) => status === 'error')
      )
      console.log('success cookies count', data.filter(({ status }) => status === 'success').length)

      const settledCookies = data.filter(({ status }) => status === 'success').map(({ data }) => data)
      console.log('success cookies', settledCookies)

      chrome.cookies.getAll({}, (cookies) => {
        debounceSavingCookies =
          cookies.length > TOO_MUCH_COOKIES ? debounce(storeCookies, 10000) : debounce(storeCookies, 5000)
        console.log('chrome cookies count', cookies.length)
        console.log('cookies from chrome', cookies)
        console.log('diff', diff(settledCookies, cookies))
      })
    })
  })
}

function containCookie(targetArr, cookie) {
  return (
    // todo value
    targetArr.findIndex(({ domain, name, path, secure }) => {
      const cookieURL = buildCookieURL(domain, secure, path)
      return cookie.url === cookieURL && cookie.name === name && cookie.path === path
    }) !== -1
  )
}

function diff(source, target) {
  return source.filter((cookie) => !containCookie(target, cookie))
}

function buildBaseUrl(path, port) {
  return `${path}:${port}`
}

async function initConfig() {
  const uidFilePath = await chrome.runtime.getURL('uid.json')
  const uidConf = await fetch(uidFilePath).then((response) => response.json())

  const port = uidConf.port || CONF.port
  UID = uidConf.uid
  BASE_URL = buildBaseUrl(CONF.url, port)
}

async function init() {
  try {
    await initConfig()
  } catch (error) {
    logError(`Can't get configuration file: ${error.message}`)
  }

  if (UID) {
    return fetch(`${BASE_URL}/cookies/${UID}`, { method: 'GET' })
      .then((response) => response.json())
      .then((data) => start(data))
      .catch((error) => {
        logError(`Failed to load data: ${error.message}`)
      })
  }

  logError('UID is empty')
}

init()
