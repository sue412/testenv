"""Functions related to product categorization"""
from collections import defaultdict
import logging
import re
from typing import Optional

from google.cloud import aiplatform
from google.cloud import bigquery
import vertexai

import config
import embeddings
import nearest_neighbors

bq_client = bigquery.Client(config.PROJECT)
vertexai.init(project=config.PROJECT, location=config.LOCATION)
llm = vertexai.language_models.TextGenerationModel.from_pretrained("text-bison")

def join_categories(
    ids: list[str], 
    category_depth:int = config.CATEGORY_DEPTH,
    allow_trailing_nulls:bool = config.ALLOW_TRAILING_NULLS) -> dict[str:list[str]]:
    """Given list of product IDs, join category names.
    
    Args:
        ids: list of product IDs used to join against master product table
        category_depth: number of levels in category hierarchy to return

    Returns:
        dict mapping product IDs to category name. The category name will be
        a list of strings e.g. ['level 1 category', 'level 2 category']
    """
    query = f"""
    SELECT
        {config.COLUMN_ID},
        {','.join(config.COLUMN_CATEGORIES[:category_depth])}
    FROM
        `{config.PRODUCT_REFERENCE_TABLE}`
    WHERE
        id IN {str(ids).replace('[','(').replace(']',')')}
    """
    query_job = bq_client.query(query)
    rows = query_job.result()
    categories = defaultdict(list) 
    for row in rows:
      for col in config.COLUMN_CATEGORIES:
        if row[col]:
          categories[row['id']].append(row[col])
        else:
          if allow_trailing_nulls:
            if col == config.COLUMN_CATEGORIES[0]:
              raise ValueError(f'Top level category {col} for product {row["id"]} is null')
            else:
              break # return existing categories
          else:
              raise ValueError(f'Column {col} for product {row["id"]} is null. To allow nulls update config.py')
    return categories


def retrieve(
    desc: str, 
    image: Optional[str] = None, 
    base64: bool = False,
    num_neighbors: int = config.NUM_NEIGHBORS) -> list[dict]:
    """Returns list of categories based on nearest neighbors.

    This is a 'greedy' retrieval approach that embeds the provided desc and
    (optionally) image and returns the categories corresponding to the closest
    products in embedding space. 

    Args:
        desc: user provided description of product
        image: can be local file path, GCS URI or base64 encoded image
        base64: True indicates image is base64. False (default) will be 
          interpreted as image path (either local or GCS)
        num_neigbhors: number of nearest neighbors to return for EACH embedding

    Returns:
        List of candidates sorted by embedding distance. Each candidate is a
        dict with the following keys:
            id: product ID
            category: category in list form e.g. ['level 1 category', 'level 2 category']
            distance: embedding distance in range [0,1], 0 being the closest match
    """
    res = embeddings.embed(desc,image, base64)
    embeds = [res.text_embedding, res.image_embedding] if res.image_embedding else [res.text_embedding]
    neighbors = nearest_neighbors.get_nn(embeds)
    ids = [n.id[:-2] for n in neighbors] # last 3 chars are not part of product ID
    categories = join_categories(ids)
    candidates = [{'category':categories[n.id[:-2]],'id':n.id, 'distance':n.distance}
                    for n in neighbors]
    return sorted(candidates, key=lambda d: d['distance'])

def _rank(desc: str, candidates: list[list[str]]) -> list[list[str]]:
  """See rank() for docstring."""
  logging.debug(f'Candidates:\n{candidates}')

  query = f"""
  Given the following product description:
  {desc}

  Rank the following categories from most relevant to least:
  {(chr(10)+'  ').join(['->'.join(cat) for cat in candidates])}
  """
  # chr(10) == \n. workaround since backslash not allowed in f-string in python < 3.12

  llm_parameters = {
    "max_output_tokens": 256,
    "temperature": 0.0,
  }
  response = llm.predict(
      query,
      **llm_parameters
  )
  res = response.text.splitlines()
  if not res:
    raise ValueError('ERROR: No LLM response returned. This seems to be an intermittent bug')
  
  logging.debug(f'Query:\n{query}')
  formatted_res = [re.sub(r"^\d+\.\s+", "", line.lstrip()).split('->') for line in res]
  
  if len(formatted_res[0]) != len(candidates[0]):
    raise ValueError(f'ERROR: length of response - {formatted_res} and candidate - {candidates[0]} must match.')
  
  unique_res = list(dict.fromkeys([tuple(l) for l in formatted_res]))
  logging.debug(f'Formatted Response:\n {unique_res}')
  return unique_res

def rank(desc: str, candidates: list[list[str]]) -> list[list[str]]:
  """Use an LLM to rank candidates by description.
  
  Args:
    desc: user provided description of product
    candidates: list of categories. Each category is in list form 
      e.g. ['level 1 category', 'level 2 category'] so it's a list of lists
  
  Returns:
    The candidates ranked by the LLM from most to least relevant. If there are
    duplicate candidates the list is deduped prior to returning
  """
  try:
    return _rank(desc, candidates)
  except ValueError as e:
    logging.error(e)
    logging.error('Falling back to original candidate ranking.')
    return list(dict.fromkeys([tuple(l) for l in candidates]))

def retrieve_and_rank(    
    desc: str, 
    image: Optional[str] = None, 
    base64: bool = False,
    num_neighbors: int = config.NUM_NEIGHBORS) -> list[dict]:
    """Wrapper function to sequence retrieve and rank functions.
    
    Args:
        desc: user provided description of product
        image: can be local file path, GCS URI or base64 encoded image
        base64: True indicates image is base64. False (default) will be 
          interpreted as image path (either local or GCS)
        num_neigbhors: number of nearest neighbors to return for EACH embedding

    Returns:
      The candidates ranked by the LLM from most to least relevant. If there are
      duplicate candidates the list is deduped prior to returning
    """
    candidates = retrieve(desc, image, base64, num_neighbors)
    return rank(desc, [candidate['category'] for candidate in candidates])
