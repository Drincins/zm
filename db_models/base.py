# db_models/base.py
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

import db_models.statement
import db_models.firm
import db_models.category
import db_models.group
import db_models.company
import db_models.up_company
import db_models.editbank
import db_models.income_expense
import db_models.income_format
import db_models.restaurant_expense
import db_models.restaurant_payment_method
import db_models.payment_method
import db_models.payment_link
import db_models.user
import db_models.user_company
import db_models.user_category
