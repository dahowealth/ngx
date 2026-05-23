library(httr)
library(rvest)
library(dplyr)
library(tibble)
library(stringr)

clean_num <- function(x) {
  x <- gsub(" ", "", x)
  x <- gsub(",", ".", x)
  x <- gsub("%", "", x)
  as.numeric(x)
}

url <- "https://www.brvm.org/fr/cours-actions/0"

res <- GET(
  url,
  add_headers("User-Agent" = "Mozilla/5.0")
)

txt <- content(res, as = "text", encoding = "UTF-8")
html <- read_html(txt)

update_text <- html |>
  html_element("#block-tools-date-maj") |>
  html_text2()

print(update_text)

trade_date_text <- str_extract(update_text, "\\d{1,2} [[:alpha:]]+[,]? \\d{4}")
trade_date_text <- gsub(",", "", trade_date_text)

month_map <- c(
  "janvier" = "01",
  "février" = "02",
  "fevrier" = "02",
  "mars" = "03",
  "avril" = "04",
  "mai" = "05",
  "juin" = "06",
  "juillet" = "07",
  "août" = "08",
  "aout" = "08",
  "septembre" = "09",
  "octobre" = "10",
  "novembre" = "11",
  "décembre" = "12",
  "decembre" = "12"
)

parts <- str_split(trade_date_text, " ", simplify = TRUE)

day_num <- str_pad(parts[1], width = 2, side = "left", pad = "0")
month_num <- month_map[str_to_lower(parts[2])]
year_num <- parts[3]

trade_date <- as.Date(paste(year_num, month_num, day_num, sep = "-"))

tables <- html |>
  html_elements("table") |>
  html_table(fill = TRUE)

main_table <- tables[[4]]

stock_data <- as_tibble(main_table, .name_repair = "unique")

names(stock_data) <- c(
  "Ticker",
  "Name",
  "Volume",
  "Prev_Close",
  "Open",
  "Close",
  "Change_pct"
)

stock_data <- stock_data |>
  mutate(
    Volume = clean_num(Volume),
    Prev_Close = clean_num(Prev_Close),
    Open = clean_num(Open),
    Close = clean_num(Close),
    Change_pct = clean_num(Change_pct),
    Trade_Date = trade_date
  )

output_dir <- "/home/ec2-user/ngx/brvm_files"

dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

file_path <- paste0(
  output_dir,
  "/brvm_",
  trade_date,
  ".csv"
)

write.csv(stock_data, file = file_path, row.names = FALSE)

print(stock_data)
print(file_path)
print("BRVM daily CSV saved successfully on EC2.")
